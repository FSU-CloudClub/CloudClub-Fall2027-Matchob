"""Split a plain-text resume into units: each bullet point, plus the skills line.

Each unit records exactly where its text sits in the original resume:
    {"id": "u1", "section": "experience", "text": "...", "start": 13, "end": 29}
so that resume[start:end] == unit["text"]. The span check relies on this to
point at the exact evidence for a "Supported" recommendation.

Positions are counted in the exact string passed in, so slice that same string.
"""


# Every heading we recognize, mapped to the section name it starts.
# Several headings can share one name: "TECHNICAL SKILLS" and "SKILLS" both
# start "skills". Any other line, even all caps like a company name such as
# "GOOGLE", is not a heading and leaves the section unchanged.
HEADINGS = {
    "EDUCATION": "education",
    "EXPERIENCE": "experience",
    "WORK EXPERIENCE": "experience",
    "PROFESSIONAL EXPERIENCE": "experience",
    "PROJECTS": "projects",
    "SKILLS": "skills",
    "TECHNICAL SKILLS": "skills",
    "CERTIFICATIONS": "certifications",
    "LEADERSHIP": "leadership",
    "AWARDS": "awards",
}


def split_resume(text: str) -> list[dict]:
    units = []
    section = None            # current section name ("experience"), from HEADINGS
    expecting_skills = False  # True right after a SKILLS heading
    pos = 0                   # running character count: where the current line starts

    # keepends=True keeps each line's line break ("\n" or "\r\n") attached, so
    # adding up line lengths gives exact positions on Windows and Mac/Linux files.
    for line in text.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        content = line.rstrip("\r\n")  # the line without its line break
        stripped = content.strip()

        if not stripped or stripped == "-":
            continue  # blank line or an empty bullet

        # Bullet: "- Built a REST API" -> unit text "Built a REST API"
        if stripped.startswith("- "):
            indent = len(content) - len(content.lstrip())  # spaces before the "-"
            after_dash = content[indent + 1:]
            gap = len(after_dash) - len(after_dash.lstrip())  # spaces after the "-"
            unit_text = after_dash.strip()
            start = line_start + indent + 1 + gap
            units.append(_unit(units, section, unit_text, start))
            expecting_skills = False
            continue

        heading = _heading(stripped)  # section name, or None if not a heading

        # The first line under SKILLS is one unit, unless it's another heading
        # (an empty SKILLS section).
        if expecting_skills and heading is None:
            start = line_start + len(content) - len(content.lstrip())
            units.append(_unit(units, section, stripped, start))
            expecting_skills = False
            continue

        # A known heading such as EXPERIENCE or TECHNICAL SKILLS
        if heading is not None:
            section = heading
            expecting_skills = section == "skills"
            continue

        # Anything else (name, contact info, job titles, dates) is not a unit.

    return units


def _heading(stripped: str) -> str | None:
    """Return the section name if this line is a known heading, else None.

    Cleans the line first so "Skills:", "SKILLS" and "TECHNICAL  SKILLS"
    (two spaces) all match.
    """
    cleaned = " ".join(stripped.upper().rstrip(":").split())
    return HEADINGS.get(cleaned)


def _unit(units: list[dict], section: str | None, unit_text: str, start: int) -> dict:
    """Build one unit dict, numbering ids u1, u2, u3... in order."""
    return {
        "id": f"u{len(units) + 1}",
        "section": section,
        "text": unit_text,
        "start": start,
        "end": start + len(unit_text),
    }