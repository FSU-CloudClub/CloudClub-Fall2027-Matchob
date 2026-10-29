"""Pull the hiring requirements out of a job posting.

`extract_requirements` fills in the v1 prompt (ai/prompts/requirement_extraction.v1.md),
sends it through `model`, and returns the `requirements` list from the reply. Each
requirement has the shape in ai/contracts/requirement.schema.json.
"""

import json
from pathlib import Path
from typing import Callable

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "requirement_extraction.v1.md"

SYSTEM_HEADING = "## System message"
USER_HEADING = "## User message"
PLACEHOLDER = "{{JOB_TEXT}}"


def _load_prompt() -> tuple[str, str]:
    """Split the prompt file into (system message, user message template)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    _, _, rest = text.partition(SYSTEM_HEADING)
    system, _, user = rest.partition(USER_HEADING)
    system, user = system.strip(), user.strip()
    if not system or PLACEHOLDER not in user:
        raise RuntimeError(f"{PROMPT_PATH} is missing its system message or {PLACEHOLDER}")
    return system, user


def extract_requirements(job_text: str, model: Callable[[str, str], str]) -> list[dict]:
    """Return the requirements the model finds in `job_text`.

    `model` takes (system message, user message) and returns the reply as text.
    Raises ValueError if the reply isn't a JSON object with a "requirements" list.
    """
    system, user_template = _load_prompt()
    # str.replace, not str.format: the template contains a JSON example full of braces.
    user = user_template.replace(PLACEHOLDER, job_text)

    reply = model(system, user)

    try:
        # TODO: swap in arturo's read_json once it's merged (it also handles
        # replies wrapped in a code block).
        data = json.loads(reply)
    except json.JSONDecodeError as err:
        raise ValueError(f"model reply is not valid JSON: {err}") from err

    if not isinstance(data, dict) or not isinstance(data.get("requirements"), list):
        raise ValueError('model reply must be a JSON object with a "requirements" list')
    return data["requirements"]