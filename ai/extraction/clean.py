import re


_SKIP_HEADING = re.compile(
    r"(?:(?:(?:our|employee|company)\s+)?(?:benefits|perks)"
    r"(?:\s*(?:and|&|/)\s*(?:benefits|perks|compensation))?|"
    r"compensation\s*(?:and|&|/)\s*benefits|"
    r"about\s+(?:us|(?:the|our)\s+company)|"
    r"equal\s+(?:employment\s+)?opportunity.*|eeo(?:\s+.*)?|"
    r"legal(?:\s+.*)?|disclaimers?)",
    re.IGNORECASE,
)
_JOB_HEADING = re.compile(
    r"(?:(?:(?:minimum|required|preferred|basic|technical)\s+)?"
    r"(?:qualifications|requirements|skills)|responsibilities|"
    r"(?:job|role)\s+(?:description|overview)|about\s+(?:the\s+)?role|"
    r"what\s+(?:you(?:'ll|\s+will)\s+do|we(?:'re|\s+are)\s+looking\s+for)|"
    r"who\s+you\s+are)",
    re.IGNORECASE,
)


def clean_posting(text: str) -> list[dict]:
    kept = []
    offset = 0
    skipping = False
    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        start = offset + len(raw) - len(raw.lstrip())
        offset += len(raw)
        if not line:
            continue
        heading = line.strip("#* \t").rstrip(":").strip()
        # shortcut: plain headings use known names; extend for new posting formats.
        if _SKIP_HEADING.fullmatch(heading):
            skipping = True
            continue
        if (
            _JOB_HEADING.fullmatch(heading)
            or line.endswith(":")
            or line.startswith("#")
            or (line.startswith("**") and line.endswith("**"))
        ):
            skipping = False
        if not skipping:
            kept.append({"text": line, "start": start, "end": start + len(line)})
    return kept

print(clean_posting("About us: world-leading finance company. We are looking for a software engineer with experience in Python and JavaScript. Benefits: 401k, flexible schedules. Experience with Go is a plus. Preferred: AWS."))