"""Split a plain-text resume into units: each bullet point, plus the skills line.

Each unit records exactly where its text sits in the original resume:
    {"id": "u1", "section": "experience", "text": "...", "start": 13, "end": 29}
so that resume[start:end] == unit["text"]. The span check relies on this to
point at the exact evidence for a "Supported" recommendation.

Positions are counted in the exact string passed in, so slice that same string.
"""


# Headings that can never be the skills line, even right under SKILLS.
KNOWN_HEADINGS = {"education", "experience", "projects", "skills"}


def split_resume(text: str) -> list[dict]:
    units = []
    section = None            # current section heading, lowercased ("experience")
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

        # The first line under SKILLS is one unit. Checked before headings, so an
        # all-caps skills line like "AWS, SQL" isn't mistaken for a heading.
        if expecting_skills and stripped.lower() not in KNOWN_HEADINGS:
            start = line_start + len(content) - len(content.lstrip())
            units.append(_unit(units, section, stripped, start))
            expecting_skills = False
            continue

        # All-caps line: a section heading such as EXPERIENCE or SKILLS
        if stripped.isupper():
            section = stripped.lower()
            expecting_skills = section == "skills"
            continue

        # Anything else (name, contact info, job titles, dates) is not a unit.

    return units


def _unit(units: list[dict], section: str | None, unit_text: str, start: int) -> dict:
    """Build one unit dict, numbering ids u1, u2, u3... in order."""
    return {
        "id": f"u{len(units) + 1}",
        "section": section,
        "text": unit_text,
        "start": start,
        "end": start + len(unit_text),
    }