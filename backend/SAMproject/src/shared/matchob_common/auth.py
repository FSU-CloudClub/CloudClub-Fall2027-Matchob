import os 

def get_user_id(event):
    """Return the caller's Cognito sub, or None if unauthenticated"""
    claims = (
        (event.get("requestContext") or {})
        .get("authorizer", {})
        .get("claims") or {}
    )
    if claims.get("sub"):
        return claims["sub"]

    # for local development to skip the cognito authorizer
    if os.environ.get("AWS_SAM_LOCAL") == "true":
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        return headers.get("x-local-user")

    return None