"""Helpers used only by the profile Lambda."""

from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from matchob_common.validators import (
    REQUIRED,
    email,
    int_between,
    non_empty_str,
    one_of,
    optional_str,
    url_list,
)

logger = Logger(child=True)

# The fields a client may send: name -> (default, validator).
# REQUIRED fields must be sent on POST; the others fall back to their default.
# Backend-only fields (userId, resumes, structuredJsonResume) are left out, so sending them is rejected.
PROFILE_FIELDS = {
    "firstname": (REQUIRED, non_empty_str),
    "lastname": (REQUIRED, non_empty_str),
    "email": (REQUIRED, email),
    "phoneNumber": (REQUIRED, non_empty_str),
    "age": (REQUIRED, int_between(13, 120)),
    "year": (REQUIRED, one_of("freshman", "sophomore", "junior", "senior", "graduate")),
    "major": (REQUIRED, non_empty_str),
    "websites": ([], url_list),
    "defaultResume": (None, optional_str),
}


def profile_exists(table, user_id):
    """Return True if the user has a profile. Used to explain a failed update condition."""
    try:
        return "Item" in table.get_item(Key={"userId": user_id}, ProjectionExpression="userId")
    except ClientError:
        logger.exception("dynamodb get_item failed")
        return False
