"""Request body validation shared by every Lambda.

A validator takes the raw value from the request body and returns the cleaned
value, or raises ValueError with a message that completes the sentence
"<field> ...", e.g. "must be a non-empty string".
"""

import copy
import re

REQUIRED = object()


def non_empty_str(value):
    """Return the trimmed string, or raise ValueError if it is not a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty string")
    return value.strip()


def email(value):
    """Return the trimmed email address, or raise ValueError if it is not one."""
    value = non_empty_str(value)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("must be a valid email address")
    return value


def int_between(low, high):
    """Build a validator for a whole number from low to high, inclusive."""
    def validate(value):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"must be a whole number from {low} to {high}")
        return value
    return validate


def one_of(*choices):
    """Build a validator that only accepts one of the given strings."""
    def validate(value):
        if value not in choices:
            raise ValueError(f"must be one of: {', '.join(choices)}")
        return value
    return validate


def url_list(value):
    """Return the trimmed list of http(s) URLs, or raise ValueError."""
    if not isinstance(value, list):
        raise ValueError("must be a list of URLs")
    urls = []
    for url in value:
        if not isinstance(url, str) or not url.strip().startswith(("http://", "https://")):
            raise ValueError("must be a list of URLs starting with http:// or https://")
        urls.append(url.strip())
    return urls


def optional_str(value):
    """Return None, or the trimmed non-empty string."""
    return None if value is None else non_empty_str(value)


def validate_fields(body, spec, partial):
    """Validate a request body against a field spec.

    Args:
        body: The parsed JSON request body.
        spec: {field: (default, validator)}. Use REQUIRED as the default for
            fields that must be sent on create. Fields not in spec are rejected.
        partial: False for create: every REQUIRED field must be sent, and
            missing optional fields get a copy of their default. True for
            update: any non-empty subset of fields is accepted.

    Returns:
        (fields, None) with the cleaned values on success, or
        (None, error_message) if the body is invalid.
    """
    if not isinstance(body, dict):
        return None, "Request body must be a JSON object"
    unknown = set(body) - set(spec)
    if unknown:
        return None, f"Unknown fields: {', '.join(sorted(unknown))}"
    fields = {}
    for field, (default, validate) in spec.items():
        if field not in body:
            if partial:
                continue
            if default is REQUIRED:
                return None, f"{field} is required"
            fields[field] = copy.deepcopy(default)
            continue
        try:
            fields[field] = validate(body[field])
        except ValueError as error:
            return None, f"{field} {error}"
    if not fields:
        return None, "Provide at least one field to update"
    return fields, None
