"""Helpers used only by the profile Lambda."""

from matchob_common.validators import (
    REQUIRED,
    email,
    int_between,
    non_empty_str,
    one_of,
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
}
