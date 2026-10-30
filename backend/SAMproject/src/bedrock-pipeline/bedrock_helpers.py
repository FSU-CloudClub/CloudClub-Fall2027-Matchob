"""Helpers used only by the suggestions Lambda. Design: docs/bedrock-pipeline/helpers.md."""

import json
import os
import re

import boto3
from botocore.config import Config
from matchob_common.validators import REQUIRED, str_length, validate_fields

# IDs from the Bedrock console, passed in by the template. See docs/bedrock-pipeline/README.md.
PROMPT_ARN = os.environ["PROMPT_ARN"]
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]
GUARDRAIL_VERSION = os.environ["GUARDRAIL_VERSION"]

# Console {{variable}} -> where its value comes from in the validated fields.
# The console prompt must use exactly these names.
PROMPT_VARIABLES = {
    "resume": lambda f: f["resumeText"],
    "job_title": lambda f: f["jobDescription"]["title"],
    "company": lambda f: f["jobDescription"]["company"] or "",
    "job_description": lambda f: f["jobDescription"]["text"],
    "supporting_context": lambda f: f["supportingContext"] or "",
}

BLOCKED_STOP_REASONS = {"guardrail_intervened", "content_filtered"}

# Bedrock ClientError code -> status. Any other code is a 500.
ERROR_STATUS = {
    "ThrottlingException": 503,
    "ServiceUnavailableException": 503,
    "ModelTimeoutException": 504,
}

# Gives up before the Lambda's 28 s timeout and API Gateway's 29 s. No retries: one retry
# of a slow call would pass 29 s, so the client retries on 503/504 instead.
bedrock = boto3.client(
    "bedrock-runtime",
    config=Config(read_timeout=25, connect_timeout=5, retries={"total_max_attempts": 1}),
)


# Field specs for validate_fields. Anything else, at either level, is rejected.
JOB_DESCRIPTION_FIELDS = {
    "title": (REQUIRED, str_length(1, 200)),
    "company": (None, str_length(1, 200)),
    "text": (REQUIRED, str_length(1, 20000)),
}


def job_description(value):
    """Return the validated job description object, or raise ValueError."""
    if not isinstance(value, dict):
        raise ValueError("must be an object with title and text")
    fields, error = validate_fields(value, JOB_DESCRIPTION_FIELDS, partial=False)
    if error:
        raise ValueError(error)
    return fields


SUGGESTION_FIELDS = {
    "resumeText": (REQUIRED, str_length(1, 20000)),
    "jobDescription": (REQUIRED, job_description),
    "supportingContext": (None, str_length(1, 2000)),
}


def prompt_variables(fields):
    """Return converse's promptVariables. Every variable is sent, "" for a missing optional field."""
    return {name: {"text": build(fields)} for name, build in PROMPT_VARIABLES.items()}


def call_bedrock(variables):
    """Run the console prompt with its guardrail and return the raw converse response."""
    return bedrock.converse(
        modelId=PROMPT_ARN,
        promptVariables=variables,
        guardrailConfig={"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION},
    )


def was_blocked(response):
    """Return True if the guardrail or a content filter stopped the reply."""
    return response.get("stopReason") in BLOCKED_STOP_REASONS


def parse_reply(response):
    """Return the model's reply as a dict, or None if it isn't a JSON object."""
    content = response.get("output", {}).get("message", {}).get("content", [])
    text = "".join(block.get("text", "") for block in content).strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        reply = json.loads(text)
    except ValueError:
        return None
    return reply if isinstance(reply, dict) else None
