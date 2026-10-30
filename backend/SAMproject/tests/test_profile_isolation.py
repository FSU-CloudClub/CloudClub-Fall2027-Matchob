"""QA isolation tests for GET /profile.

These check that a user can only ever read their own profile:
- the local X-Local-User header works only when AWS_SAM_LOCAL is "true"
  (sam local sets it; AWS never does)
- real Cognito claims always win over the header
- a user ID in the query string, path or body never changes whose
  profile is read

These call lambda_handler in src/dynamodb-pipeline/app.py directly with
a fake API Gateway event and a fake DynamoDB table, so neither the API
nor Docker needs to be running.
"""

import json
import os
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Locate the Lambda source directory
LAMBDA_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dynamodb-pipeline"
)

sys.path.insert(0, str(LAMBDA_DIR))

# Set environment variables before importing app.py
os.environ["USERS_TABLE"] = "MatchobUsers"
os.environ["UPLOAD_BUCKET"] = "matchob-uploads"


@dataclass
class FakeLambdaContext:
    """Stand-in for the context AWS passes to a Lambda.

    The handler's Powertools logger reads these four fields, so passing
    None crashes before the handler
    code runs.
    """

    function_name: str = "GetProfileFunction"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = (
        "arn:aws:lambda:us-east-1:123456789012:function:GetProfileFunction"
    )
    aws_request_id: str = "qa-test-request"


SARAH = {
    "Item": {
        "userId": "12345",
        "name": "Sarah",
        "education": "Florida State University",
    }
}


class TestProfileIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prevent real AWS clients from being created during module import
        with patch("boto3.resource"), patch("boto3.client"):
            import app
            cls.app = app
            cls.app = app

    def setUp(self):
        # Replace the table with a fake table
        self.mock_table = MagicMock()
        self.table_patcher = patch.object(
            self.app, "table", self.mock_table
        )
        self.table_patcher.start()
        self.addCleanup(self.table_patcher.stop)

        self.context = FakeLambdaContext()

    # Helpers

    def call(self, event):
        return self.app.lambda_handler(event, self.context)

    def local_mode(self):
        """Run as sam local does: AWS_SAM_LOCAL="true"."""
        return patch.dict(os.environ, {"AWS_SAM_LOCAL": "true"})

    def production_mode(self):
        """Run as AWS does: AWS_SAM_LOCAL not set at all.

        patch.dict restores the original environment when the test ends,
        so removing the variable here doesn't affect other tests.
        """
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("AWS_SAM_LOCAL", None)

    @staticmethod
    def base_event():
        """A GET /profile request shaped like API Gateway sends it.

        The handler routes requests with Powertools' APIGatewayRestResolver,
        which needs httpMethod and path to find the GET /profile route.
        """
        return {
            "httpMethod": "GET",
            "path": "/profile",
            "resource": "/profile",
            "headers": {},
            "queryStringParameters": None,
            "pathParameters": None,
            "body": None,
            "isBase64Encoded": False,
            "requestContext": {},
        }

    @classmethod
    def header_event(cls, user_id):
        event = cls.base_event()
        event["headers"] = {"X-Local-User": user_id}
        return event

    @classmethod
    def claims_event(cls, user_id):
        event = cls.base_event()
        event["requestContext"] = {
            "authorizer": {"claims": {"sub": user_id}}
        }
        return event

    # The three checks from the task, through the local header

    def test_local_header_reads_own_profile(self):
        self.mock_table.get_item.return_value = SARAH

        with self.local_mode():
            result = self.call(self.header_event("12345"))

        self.assertEqual(result["statusCode"], 200)
        self.assertIn("Sarah", result["body"])
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "12345"}
        )

    def test_local_header_missing_profile_returns_404(self):
        self.mock_table.get_item.return_value = {}

        with self.local_mode():
            result = self.call(self.header_event("99999"))

        self.assertEqual(result["statusCode"], 404)
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "99999"}
        )

    def test_no_header_and_no_claims_returns_401(self):
        # Give the fake table data anyway, so a bug shows up as a clean
        # "200 != 401" failure instead of the handler choking on a mock.
        self.mock_table.get_item.return_value = SARAH

        with self.local_mode():
            result = self.call(self.base_event())

        self.assertEqual(result["statusCode"], 401)
        self.mock_table.get_item.assert_not_called()

    # Rules from auth.md

    def test_sequential_cognito_users_read_their_own_profiles(self):
        self.production_mode()
        profiles = {
            "12345": SARAH["Item"],
            "99999": {"userId": "99999", "name": "Alex", "education": "Other University"},
        }
        # Return data for the requested key, so a wrong-user lookup cannot
        # accidentally receive the expected profile from a fixed mock response.
        self.mock_table.get_item.side_effect = lambda *, Key: {
            "Item": profiles[Key["userId"]]
        }

        # Reuse the same Lambda module across requests to catch cached identities.
        for user_id in ("12345", "99999", "12345"):
            with self.subTest(user_id=user_id):
                result = self.call(self.claims_event(user_id))
                self.assertEqual(result["statusCode"], 200)
                self.assertEqual(json.loads(result["body"]), profiles[user_id])

        self.assertEqual(self.mock_table.get_item.call_args_list, [
            call(Key={"userId": "12345"}),
            call(Key={"userId": "99999"}),
            call(Key={"userId": "12345"}),
        ])

    def test_header_ignored_when_not_running_locally(self):
        # In production AWS_SAM_LOCAL is never set, so the header must
        # do nothing. Otherwise anyone could pick their user ID.
        self.mock_table.get_item.return_value = SARAH
        self.production_mode()

        result = self.call(self.header_event("12345"))

        self.assertEqual(result["statusCode"], 401)
        self.mock_table.get_item.assert_not_called()

    def test_claims_take_priority_over_header(self):
        self.mock_table.get_item.return_value = SARAH
        event = self.claims_event("12345")
        event["headers"] = {"X-Local-User": "99999"}

        with self.local_mode():
            result = self.call(event)

        self.assertEqual(result["statusCode"], 200)
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "12345"}
        )

    def test_query_string_cannot_change_user(self):
        self.mock_table.get_item.return_value = SARAH
        event = self.claims_event("12345")
        event["queryStringParameters"] = {"userId": "99999"}

        result = self.call(event)

        self.assertEqual(result["statusCode"], 200)
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "12345"}
        )

    def test_path_and_body_cannot_change_user(self):
        self.mock_table.get_item.return_value = SARAH
        event = self.claims_event("12345")
        event["pathParameters"] = {"userId": "99999"}
        event["body"] = '{"userId": "99999"}'

        result = self.call(event)

        self.assertEqual(result["statusCode"], 200)
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "12345"}
        )

    def test_foreign_user_in_actual_url_is_rejected_without_database_access(self):
        """P3-1: change the actual URL, not just API Gateway pathParameters."""
        self.production_mode()
        self.mock_table.get_item.return_value = {
            "Item": {"userId": "99999", "name": "PRIVATE_FOREIGN_PROFILE"}
        }
        event = self.claims_event("12345")
        event["path"] = "/profile/99999"
        event["resource"] = "/profile/{userId}"
        event["pathParameters"] = {"userId": "99999"}

        result = self.call(event)

        self.assertEqual(result["statusCode"], 404)
        self.assertNotIn("PRIVATE_FOREIGN_PROFILE", result["body"])
        self.assertNotIn("99999", result["body"])
        self.assertEqual(self.mock_table.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
