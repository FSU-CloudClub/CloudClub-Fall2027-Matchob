"""Request and response helpers shared by every Lambda."""

import json
from decimal import Decimal


def read_json_body(current_event):
    """Parse the request body as JSON.

    Args:
        current_event: app.current_event from the Powertools resolver.

    Returns:
        (body, None) on success, where body may be any JSON value or None for
        an empty body, or (None, error_message) if the body is not valid JSON.
    """
    try:
        return current_event.json_body, None
    except (ValueError, TypeError):
        return None, "Invalid JSON body"


def decimal_to_number(value):
    """json.dumps hook: DynamoDB returns numbers as Decimal, send them as JSON numbers."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def to_json(body):
    """Response serializer: pass as APIGatewayRestResolver(serializer=to_json)
    so Decimal values from DynamoDB don't become strings."""
    return json.dumps(body, default=decimal_to_number, separators=(",", ":"))
