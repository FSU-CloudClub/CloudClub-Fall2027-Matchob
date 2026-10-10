
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, Response, jsonify, request

# LOCAL TESTING ONLY. Never import this server into production code.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/local-test-pool"
CLIENT_ID = "matchob-local-client"

# Generate a fresh test-only key pair each time this server starts.
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
public_key = private_key.public_key()

# Configure boto3 BEFORE importing the existing Lambda.
# This server runs on your Mac, so it uses localhost rather than
# the Docker hostname matchob-dynamodb.
os.environ["USERS_TABLE"] = "MatchobUsers"
os.environ["DYNAMODB_ENDPOINT"] = "http://127.0.0.1:8000"
os.environ["AWS_ACCESS_KEY_ID"] = "local"
os.environ["AWS_SECRET_ACCESS_KEY"] = "local"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

lambda_path = PROJECT_ROOT / "src" / "get-profile" / "app.py"
spec = importlib.util.spec_from_file_location("matchob_get_profile", lambda_path)
lambda_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lambda_module)

app = Flask(__name__)


def create_test_token(user_id="12345", expires_in_minutes=30):
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "sub": user_id,
            "iss": ISSUER,
            "client_id": CLIENT_ID,
            "token_use": "access",
            "iat": now,
            "exp": now + timedelta(minutes=expires_in_minutes),
        },
        private_key,
        algorithm="RS256",
    )


def verify_token(token):
    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=ISSUER,
        options={
            "require": [
                "sub", "iss", "exp", "iat",
                "client_id", "token_use"
            ]
        },
    )

    if claims["client_id"] != CLIENT_ID:
        raise jwt.InvalidTokenError("Wrong client ID")

    if claims["token_use"] != "access":
        raise jwt.InvalidTokenError("Wrong token type")

    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise jwt.InvalidTokenError("Invalid subject")

    return claims


@app.get("/profile")
def get_profile():
    authorization = request.headers.get("Authorization", "")

    scheme, separator, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not separator or not token.strip():
        return jsonify({"error": "Missing bearer token"}), 401

    try:
        claims = verify_token(token.strip())
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Only verified claims are forwarded to the Lambda.
    event = {
        "httpMethod": "GET",
        "path": "/profile",
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
    }

    result = lambda_module.lambda_handler(event, None)

    return Response(
        response=result.get("body", ""),
        status=result.get("statusCode", 500),
        content_type=result.get("headers", {}).get(
            "Content-Type", "application/json"
        ),
    )


@app.get("/dev-token")
def dev_token():
    # Test-only token issuer. Never expose this on a public server.
    user_id = request.args.get("sub", "12345")
    return jsonify({"token": create_test_token(user_id)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
