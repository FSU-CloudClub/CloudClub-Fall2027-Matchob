
import os
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Locate the Lambda source directory
LAMBDA_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "get-profile"
)

sys.path.insert(0, str(LAMBDA_DIR))

# Set environment variable before importing app.py
os.environ["USERS_TABLE"] = "MatchobUsers"


class TestGetProfile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Prevent real AWS calls during module import
        with patch("boto3.resource") as mock_resource:
            import app
            cls.app = app

    def setUp(self):
        # Replace the table with a fake table
        self.mock_table = MagicMock()
        self.table_patcher = patch.object(
            self.app, "table", self.mock_table
        )
        self.table_patcher.start()
        self.addCleanup(self.table_patcher.stop)

        # Simulate verified Cognito claims
        self.event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "12345"
                    }
                }
            }
        }

    def test_existing_profile(self):
        # Pretend DynamoDB found Sarah
        self.mock_table.get_item.return_value = {
            "Item": {
                "userId": "12345",
                "name": "Sarah",
                "education": "Florida State University"
            }
        }

        result = self.app.lambda_handler(
            self.event, None
        )

        self.assertEqual(result["statusCode"], 200)

        body = json.loads(result["body"])
        self.assertEqual(body["name"], "Sarah")

        # Verify the correct user was requested
        self.mock_table.get_item.assert_called_once_with(
            Key={"userId": "12345"}
        )

    def test_missing_profile(self):
        # DynamoDB returns no Item
        self.mock_table.get_item.return_value = {}

        result = self.app.lambda_handler(
            self.event, None
        )

        self.assertEqual(result["statusCode"], 404)

    def test_unauthenticated_request(self):
        # No verified Cognito claims
        event = {"requestContext": {}}

        result = self.app.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 401)
        self.mock_table.get_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
