import json


def read_json(text):
    """Parse JSON from a model reply, allowing surrounding prose or fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character in "{[":
            try:
                value, _ = decoder.raw_decode(text, index)
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("No valid JSON found in model reply")


def call_model(system, user):
    import os
    import boto3  # inside the function, not at the top, so tests never need boto3
    """
    The other steps take model = call_model(...) and then model.reply(...) and tests pass a fake model object.
    """

    client = boto3.client("bedrock-runtime")
    model_id = os.environ["BEDROCK_MODEL_ID"]

    resp = client.converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": 4096},
    )

    blocks = resp["output"]["message"]["content"]
    return next(b["text"] for b in blocks if "text" in b)

