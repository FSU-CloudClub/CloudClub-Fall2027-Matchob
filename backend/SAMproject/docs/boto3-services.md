# Using boto3: DynamoDB, S3, Bedrock

**Purpose:** The standard way our Lambdas talk to AWS services.
**Tech:** Python, boto3 (AWS SDK).
**Role in the project:** Each client is set up so the same code works locally (Compose containers) and in AWS. Only the env vars differ.

## Clients (top of `app.py`, outside the handler)

```python
import os                                                       # env vars
import boto3                                                    # AWS SDK
from botocore.config import Config                              # client options
from botocore.exceptions import ClientError                     # AWS error type

# DynamoDB
dynamodb = boto3.resource(                                      # high-level DynamoDB API
    "dynamodb",
    endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None,   # local: http://dynamodb:8000, AWS: "" → None → real service
)
table = dynamodb.Table(os.environ["USERS_TABLE"])               # handle to our table

# S3
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT") or None,         # local: http://s3:9090
    config=Config(s3={"addressing_style": "path"}),             # s3mock needs bucket in the URL path
)
BUCKET = os.environ["UPLOAD_BUCKET"]                            # bucket name (declare in Globals + env.json)

# Bedrock
bedrock = boto3.client("bedrock-runtime")                       # no local endpoint: always real AWS
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]                       # e.g. anthropic.claude-opus-5-5
```

Clients are created **outside** `lambda_handler` so warm invocations reuse them.

## DynamoDB

```python
table.put_item(Item={"userId": user_id, "name": "Sarah"})      # create or fully replace an item

resp = table.get_item(Key={"userId": user_id})                  # read one item by partition key
item = resp.get("Item")                                         # None if it doesn't exist

table.update_item(                                              # change some fields only
    Key={"userId": user_id},                                    # which item
    UpdateExpression="SET #n = :name",                          # what to change
    ExpressionAttributeNames={"#n": "name"},                    # "name" is a reserved word, so alias it
    ExpressionAttributeValues={":name": "Sarah B"},             # values always go here, never inline
)

table.delete_item(Key={"userId": user_id})                      # delete one item
```

Numbers come back as `Decimal`, not `int`/`float`.

## S3

```python
key = f"users/{user_id}/resume.pdf"                              # prefix keys with the caller's user id

s3.put_object(Bucket=BUCKET, Key=key, Body=data,                # upload bytes
              ContentType="application/pdf")                    # stored content type

obj = s3.get_object(Bucket=BUCKET, Key=key)                     # download
data = obj["Body"].read()                                       # bytes

url = s3.generate_presigned_url(                                # temporary URL the frontend uploads to directly
    "put_object",                                               # operation the URL allows
    Params={"Bucket": BUCKET, "Key": key},                      # where it goes
    ExpiresIn=300,                                              # valid for 5 minutes
)
```

`user_id` always comes from `get_user_id(event)`, never from the request body. Locally, presigned URLs contain `http://s3:9090`, which only resolves inside containers, not in your browser.

## Bedrock

```python
resp = bedrock.converse(                                        # one request/response to a model
    modelId=MODEL_ID,                                           # model ID enabled in our account/region
    system=[{"text": "You are a resume reviewer."}],            # instructions (optional)
    messages=[{"role": "user", "content": [{"text": prompt}]}], # the conversation
    inferenceConfig={"maxTokens": 4096},                        # output cap; keep under the 29s API timeout
)
blocks = resp["output"]["message"]["content"]                   # list of content blocks
text = next(b["text"] for b in blocks if "text" in b)           # first text block (skips reasoning blocks)
stop = resp["stopReason"]                                       # "max_tokens" means the answer was cut off
```

- Copy the exact model ID from the Bedrock console (Model catalog) for our region. Some accounts need the inference-profile form (`us.` prefix).
- **Locally this calls real AWS and costs money.** SAM passes your AWS profile into the Lambda container.
- Raise the function's `Timeout` for Bedrock calls (see [adding-lambda-functions.md](adding-lambda-functions.md)).

## Errors

```python
try:
    table.get_item(Key={"userId": user_id})                     # any boto3 call
except ClientError as e:                                        # all AWS service errors
    code = e.response["Error"]["Code"]                          # e.g. ResourceNotFoundException, NoSuchKey, ThrottlingException
    logger.exception("aws call failed", extra={"code": code})   # log it (see powertools.md)
    return {"error": "Internal server error"}, 500              # never return AWS error text to clients
```
