import re

"""
Regular expressions for identifying sections to skip in the
job posting.
"""
_SKIP_HEADING = re.compile(
    r"(?:(?:(?:our|employee|company)\s+)?(?:benefits|perks)"
    r"(?:\s*(?:and|&|/)\s*(?:benefits|perks|compensation))?|"
    r"compensation\s*(?:and|&|/)\s*benefits|"
    r"about\s+(?:us|(?:the|our)\s+company)|"
    r"equal\s+(?:employment\s+)?opportunity.*|eeo(?:\s+.*)?|"
    r"legal(?:\s+.*)?|disclaimers?)",
    re.IGNORECASE,
)

"""
Regular expression for identifying job-related headings in the
job posting.
"""
_JOB_HEADING = re.compile(
    r"(?:(?:(?:minimum|required|preferred|basic|technical)\s+)?"
    r"(?:qualifications|requirements|skills)|responsibilities|"
    r"(?:job|role)\s+(?:description|overview)|about\s+(?:the\s+)?role|"
    r"what\s+(?:you(?:'ll|\s+will)\s+do|we(?:'re|\s+are)\s+looking\s+for)|"
    r"who\s+you\s+are)",
    re.IGNORECASE,
)

def clean_posting(text: str) -> list[dict]:
    """
    Return kept lines with original source offsets and their section heading.
    Lines before the first heading have an empty heading.
    """
    kept = []
    offset = 0
    skipping = False
    section_heading = ""
    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        start = offset + len(raw) - len(raw.lstrip())
        offset += len(raw)
        if not line:
            continue
        heading = line.strip("#* \t").rstrip(":").strip()
        # shortcut: plain headings use known names; extend for new posting formats.
        if _SKIP_HEADING.fullmatch(heading.split(":", 1)[0].strip()):
            skipping = True
            continue
        if (
            _JOB_HEADING.fullmatch(heading)
            or line.startswith("#")
            or (line.startswith("**") and line.endswith("**"))
        ):
            skipping = False
            section_heading = line
        if not skipping:
            kept.append({
                "text": line,
                "start": start,
                "end": start + len(line),
                "heading": section_heading,
            })
    return kept
