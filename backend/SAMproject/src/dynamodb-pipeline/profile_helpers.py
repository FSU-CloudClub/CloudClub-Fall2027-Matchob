"""Helpers used only by the profile Lambda."""

from matchob_common.validators import (
    REQUIRED,
    email,
    int_between,
    non_empty_str,
    one_of,
    optional_str,
    url_list,
)

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
    """Check existence; let AWS failures propagate rather than imply a missing item."""
    return "Item" in table.get_item(Key={"userId": user_id}, ProjectionExpression="userId")
