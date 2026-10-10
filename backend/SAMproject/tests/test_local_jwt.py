import jwt
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate a temporary RSA key pair for local testing.
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
public_key = private_key.public_key()

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/local-test-pool"
CLIENT_ID = "matchob-local-client"


def create_token(user_id="12345", expires_in_minutes=30):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes)
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


def verify_token(token):
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=ISSUER,
        options={"require": ["sub", "iss", "exp", "client_id", "token_use"]}
    )


token = create_token()
print("Generated JWT:", token)

claims = verify_token(token)

assert claims["client_id"] == CLIENT_ID
assert claims["token_use"] == "access"

print("\nJWT verified successfully!")
print("Authenticated user ID:", claims["sub"])

# TEST 1: Expired token
expired_token = create_token(expires_in_minutes=-1)

try:
    verify_token(expired_token)
    print("FAIL: Expired token was accepted")
except jwt.ExpiredSignatureError:
    print("PASS: Expired token rejected")


# TEST 2: Tampered token
parts = token.split(".")
tampered_token = parts[0] + "." + parts[1][:-1] + (
    "A" if parts[1][-1] != "A" else "B"
) + "." + parts[2]

try:
    verify_token(tampered_token)
    print("FAIL: Tampered token was accepted")
except jwt.InvalidTokenError:
    print("PASS: Tampered token rejected")


# TEST 3: Wrong issuer
wrong_issuer_token = jwt.encode(
    {
        "sub": "12345",
        "iss": "https://fake-issuer.example.com",
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    },
    private_key,
    algorithm="RS256",
)

try:
    verify_token(wrong_issuer_token)
    print("FAIL: Wrong issuer was accepted")
except jwt.InvalidIssuerError:
    print("PASS: Wrong issuer rejected")


# TEST 4: Wrong signing key
other_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

wrong_key_token = jwt.encode(
    {
        "sub": "12345",
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    },
    other_private_key,
    algorithm="RS256",
)

try:
    verify_token(wrong_key_token)
    print("FAIL: Wrong signing key was accepted")
except jwt.InvalidSignatureError:
    print("PASS: Wrong signing key rejected")