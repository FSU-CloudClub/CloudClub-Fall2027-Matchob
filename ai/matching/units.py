"""Split a resume's text into units: each bullet point, plus the skills line.

Each unit records exactly where its text sits in the original resume:
    {"id": "u1", "section": "experience", "text": "...", "start": 13, "end": 29}
so that resume[start:end] == unit["text"]. The span check relies on this to
point at the exact evidence for a "Supported" recommendation, and the screen
uses it to highlight the bullet.

Works on clean .txt resumes ("- " before each bullet) and on the text the PDF
parser pulls out, where:
  - bullet markers are gone, so a bullet is any line under EXPERIENCE,
    PROJECTS and similar sections that isn't a job or project header;
  - long bullets wrap onto the next line, and that line is joined back on;
  - the skills line wraps too ("... AWS" / "Lambda, Linux"), and is joined back.

A unit that was joined from two lines keeps the line break inside its text,
so resume[start:end] == unit["text"] stays true.

Positions are counted in the exact string passed in, so slice that same string.
"""

import re


# Headings are found by their last word, so the many ways resumes name a
# section all work: "EXPERIENCE", "NURSING EXPERIENCE" and "ACADEMIC EXPERIENCE"
# are all experience; "SKILLS", "PERSONAL SKILLS", "SOFTWARE" and
# "CORE COMPETENCIES" are all skills; "RESEARCH & PROJECTS" is projects.
# Using the last word keeps a job title like "Software Engineer" from counting
# as a skills heading. Only short, heading-looking lines are checked (see
# _heading), so a bullet like "Gained experience in sales" never counts, and
# "GOOGLE" isn't a heading because its last word isn't one of these.
SECTION_WORDS = {
    "experience": {"EXPERIENCE", "EMPLOYMENT", "HISTORY", "RESEARCH"},
    "projects": {"PROJECT", "PROJECTS"},
    "skills": {"SKILL", "SKILLS", "SOFTWARE", "COMPETENCY", "COMPETENCIES",
               "TECHNOLOGIES", "TOOLS", "LANGUAGES"},
    "education": {"EDUCATION", "ACADEMICS"},
    "certifications": {"CERTIFICATION", "CERTIFICATIONS", "LICENSE", "LICENSES", "LICENSURE"},
    "leadership": {"LEADERSHIP", "ACTIVITIES", "INVOLVEMENT", "VOLUNTEER", "VOLUNTEERING"},
    "awards": {"AWARD", "AWARDS", "HONOR", "HONORS", "HONOURS"},
    # Sections with no bullets or skills. They still count as headings, so the
    # section above them ends: "INTERESTS" after SKILLS isn't read as more skills.
    "other": {"SUMMARY", "OBJECTIVE", "PROFILE", "INTERESTS", "HOBBIES",
              "PUBLICATIONS", "REFERENCES", "COURSEWORK"},
}
LAST_WORD_TO_SECTION = {word: section for section, words in SECTION_WORDS.items() for word in words}

# A heading has at most this many words: "PROFESSIONAL WORK EXPERIENCE" fits.
HEADING_MAX_WORDS = 4

# Small words a Title Case heading can leave lowercase: "Honors and Awards".
HEADING_SMALL_WORDS = {"and", "of", "the", "for", "&", "/"}

# Sections where a plain line (no marker) is a bullet. Not education: lines
# like "GPA 3.6" or "Relevant coursework: ..." are details, not bullets.
BULLET_SECTIONS = {"experience", "projects", "leadership"}

# A bullet marker at the start of a line, followed by a space: - • – — ▪ ◦ ● · *
# "-" covers our .txt files; PDFs use the rest. "-5 degrees" has no space, so no marker.
MARKER = re.compile(r"[-\u2022\u2013\u2014\u25aa\u25e6\u25cf\u00b7*] ")

# A job or project header ends with a date: "Jan 2026 - Present", "Mar 2026",
# "Summer 2026". Bullets end with a period or a word, so they don't match.
HEADER_DATE = re.compile(r"(?:\b(?:19|20)\d{2}|\bPresent)$", re.IGNORECASE)

# Invisible characters PDFs leave behind: soft hyphen, zero-width spaces.
INVISIBLE = "\u00ad\u200b\u200c\u200d\ufeff"

# A bullet line that ends with one of these is finished; the next line is not
# a continuation of it.
SENTENCE_END = (".", "!", "?")


def split_resume(text: str) -> list[dict]:
    lines = list(_lines(text))
    has_markers = any(MARKER.match(stripped) for _, _, stripped in lines)

    units = []
    section = None        # current section name ("experience"), from the last heading
    open_unit = None      # the last unit, while the next line may still join it
    expecting_skills = False  # True right after a SKILLS heading

    for start, end, stripped in lines:
        if _is_blank(stripped) or stripped == "-":
            open_unit = None  # a blank line or an empty bullet ends the unit
            continue

        heading = _heading(stripped)  # section name, or None if not a heading
        if heading is not None:
            section = heading
            expecting_skills = section == "skills"
            open_unit = None
            continue

        marker = MARKER.match(stripped)

        # A line that continues the unit above it: a wrapped bullet or a
        # wrapped skills line. It's joined on by moving the unit's end.
        if open_unit is not None and not marker and _continues(open_unit, stripped):
            _extend(open_unit, text, end)
            continue

        # Bullet with a marker: "- Built a REST API" -> "Built a REST API"
        if marker:
            after = stripped[marker.end():]
            gap = len(after) - len(after.lstrip())  # extra spaces after the marker
            open_unit = _add(units, section, text, start + marker.end() + gap, end)
            expecting_skills = False
            continue

        # The first line under SKILLS starts the skills unit. The lines right
        # after it join on (see _continues), so "AWS" / "Lambda" stays one skill.
        if expecting_skills:
            open_unit = _add(units, section, text, start, end)
            expecting_skills = False
            continue

        # Without markers (PDF text), a plain line under EXPERIENCE or PROJECTS
        # is a bullet, unless it's a job or project header ending in a date.
        if not has_markers and section in BULLET_SECTIONS and not HEADER_DATE.search(stripped):
            open_unit = _add(units, section, text, start, end)
            continue

        # Anything else (name, contact info, job titles, dates) is not a unit.
        open_unit = None

    return units


def _lines(text: str):
    """Yield (start, end, stripped) for each line.

    start and end are the positions of the line's text without its line break
    and without spaces at either end, so text[start:end] == stripped.
    """
    pos = 0
    # keepends=True keeps each line's line break ("\n" or "\r\n") attached, so
    # adding up line lengths gives exact positions on Windows and Mac/Linux files.
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")  # the line without its line break
        stripped = content.strip()
        start = pos + len(content) - len(content.lstrip())
        yield start, start + len(stripped), stripped
        pos += len(line)


def _continues(unit: dict, stripped: str) -> bool:
    """True if this line is the rest of the unit above it, not a new one."""
    if unit["section"] == "skills":
        return True  # every line of the skills block belongs to one unit
    if unit["text"].endswith(SENTENCE_END):
        return False  # the bullet above already finished its sentence
    # A wrapped line goes on mid-sentence, so it starts lowercase:
    # "...compressing images and" / "splitting code."
    return stripped[0].islower()


def _heading(stripped: str) -> str | None:
    """Return the section name if this line is a heading, else None.

    A heading is a short line of only letters (plus & / - and '), in ALL CAPS
    or Title Case, with an optional colon at the end. Its last word names the
    section: "Technical Skills:", "TECHNICAL  SKILLS" and "SOFTWARE" are skills.
    """
    cleaned = stripped.rstrip(":").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z&/'\s-]*", cleaned):
        return None  # digits, commas or periods: a sentence, a list or a date line
    words = cleaned.split()
    if len(words) > HEADING_MAX_WORDS:
        return None
    title_case = all(w[0].isupper() or w.lower() in HEADING_SMALL_WORDS for w in words)
    if not (cleaned.isupper() or title_case):
        return None  # "Gained experience" is a sentence, not a heading
    last_word = re.findall(r"[A-Za-z]+", cleaned)[-1].upper()
    return LAST_WORD_TO_SECTION.get(last_word)


def _is_blank(stripped: str) -> bool:
    """True for an empty line, or one holding only invisible PDF characters."""
    return not "".join(c for c in stripped if c not in INVISIBLE).strip()


def _add(units: list[dict], section: str | None, text: str, start: int, end: int) -> dict:
    """Add a unit for text[start:end], numbering ids u1, u2, u3... in order."""
    unit = {
        "id": f"u{len(units) + 1}",
        "section": section,
        "text": text[start:end],
        "start": start,
        "end": end,
    }
    units.append(unit)
    return unit


def _extend(unit: dict, text: str, end: int) -> None:
    """Join the next line onto a unit: its text now runs to the new end."""
    unit["end"] = end
    unit["text"] = text[unit["start"]:unit["end"]]