"""Label a rewritten resume bullet as supported, needs_confirmation or unsupported."""

import re
from decimal import ROUND_HALF_UP, Decimal

from ai.guardrails.claims import (FACTORS, find_changes, find_help_words, find_multipliers,
                                  find_numbers, find_outcomes, find_scope_words, find_time_units,
                                  find_titles, find_tools)
from ai.guardrails.span_check import span_exists
from ai.guardrails.text import clean
from ai.matching.normalize import normalize

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by", "from", "as",
    "that", "which", "who", "while", "into", "over", "per", "is", "was", "were", "be", "been", "it",
    "its", "this", "these", "their", "my", "our", "up",
}


CLOSE = Decimal("0.95")  # 1.9x for "doubled" is close but short; 1.75x is not close


def _share(before: Decimal, after: Decimal, factor: Decimal) -> Decimal:
    """How much of the claimed change the numbers show; 1 or more means the word fits."""
    ratio = after / before
    if factor >= 1:
        return ratio / factor
    return factor / ratio if ratio else Decimal(1)


def _is_change_percent(number: str, changes: list[tuple[Decimal, Decimal]]) -> bool:
    """A worked-out percent is backed when it is the real change, exact to the digits it shows:
    "65%" for 850 to 1,400 (64.7%), "53%" for a cut from 30 to 14. Close is not enough."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)%", number)
    if not match:
        return False
    claim = Decimal(match[1])
    step = Decimal(1).scaleb(claim.as_tuple().exponent)  # "65" rounds to 1, "64.7" to 0.1
    return any(abs((after - before) / before * 100).quantize(step, ROUND_HALF_UP) == claim
               for before, after in changes)


# A line that only lists what you know. A tool named only on such lines is weak evidence, so a
# rewrite that claims you used it needs confirmation. "Project: Built..." and "Tech stack:" are
# not labels: they describe real work.
SKILLS_LABEL = re.compile(
    r"\s*(?:[-*•–▪]\s*)?(?:(?:technical )?skills|software|tools|programming languages|technologies"
    r"|frameworks|coursework|certifications?)\s*:", re.IGNORECASE)


SKILLS_HEADING = re.compile(r"(?:technical |computer )?skills(?: ?(?:&|and) [a-z ]+)?:?", re.IGNORECASE)
HEADINGS = {"experience", "work experience", "projects", "education", "leadership", "activities",
            "involvement", "volunteer", "research", "awards", "honors", "certifications",
            "publications", "interests"}


def _is_heading(line: str) -> bool:
    """A section name ("Experience", "PROJECTS:") or an all-caps line of 2+ words with no comma.
    A lone all-caps skill like "SQL" is not a heading, so it can't end the Skills section early."""
    text = line.strip().rstrip(":").strip()
    return text.casefold() in HEADINGS or (text.isupper() and len(text.split()) > 1 and "," not in text)


def _used_text(resume: str) -> str:
    """The resume without its Skills lines: everything from a Skills heading to the next heading,
    and labelled lines anywhere ("Software: Power BI"). A tool in what's left shows it was used."""
    # ponytail: check_recommendation's narrowed source has no Skills heading, so there only
    # labelled lines are recognized; pass the whole resume's Skills lines in if that matters.
    used, in_skills = [], False
    for line in resume.splitlines():
        if SKILLS_HEADING.fullmatch(line.strip()) or _is_heading(line):
            in_skills = bool(SKILLS_HEADING.fullmatch(line.strip()))
            used.append(line)  # a heading names no tools
        elif not in_skills and not SKILLS_LABEL.match(line):
            used.append(line)
    return "\n".join(used)


def _stems(text: str) -> set[str]:
    """First five letters of each content word: not a stopword, has a letter, not a pure number."""
    words = re.findall(r"\w+", normalize(text))
    return {w[:5] for w in words if re.search(r"[^\W\d_]", w) and w not in STOPWORDS}


def classify(suggestion: str, resume: str, evidence: str = "") -> dict:
    """Return a preliminary rule label; resume and user-note text are data, never instructions.

    Guarantees: an empty suggestion is unsupported; every number, tool, title and time unit in
    the suggestion is in the source (fine), only in the note (needs_confirmation) or nowhere
    (unsupported); a result verb needs a result in the source; dropping "helped" needs
    confirmation; and a suggestion whose wording
    is mostly new needs confirmation, so "no rule fired" is no longer enough for supported.
    Does not guarantee meaning: a reworded fact, or a different result, can still pass. It also
    does not produce the frontend's evidence-span contract. The caller decides what the source
    is; see check_recommendation for the safe way to build it.
    """
    used = clean(_used_text(resume))  # before clean() joins the lines into one
    suggestion, resume, evidence = clean(suggestion), clean(resume), clean(evidence)
    if not re.search(r"\w", suggestion):
        return {"status": "unsupported", "reasons": ["There is no suggestion to check"]}
    unsupported, confirm = [], []

    if not re.search(r"\w", resume):
        if re.search(r"\w", evidence):
            confirm.append("Only your note backs this")
        else:
            unsupported.append("Nothing in your resume backs this")

    # Numbers and tools: only in the user's own note -> ask them; nowhere -> invented.
    # A percent worked out from the resume's own "from A to B" counts as in the resume.
    # ponytail: any "from A to B" in the source counts, so on a whole resume another bullet's
    # numbers can back this one; check_recommendation's narrowed source avoids that.
    resume_numbers, note_numbers = find_numbers(resume), find_numbers(evidence)
    changes = find_changes(resume)
    for number in find_numbers(suggestion):
        if number in resume_numbers or _is_change_percent(number, changes):
            continue
        if number in note_numbers:
            confirm.append(f"{number} is only in your note")
        else:
            unsupported.append(f"{number} is not in your resume")

    # Growth words are number claims too: "doubled" needs the resume to say it, or to show it
    # with "from A to B". Within 5% of the claim needs confirmation; further short is invented.
    for word in sorted(find_multipliers(suggestion) - find_multipliers(resume)):
        best = max((_share(before, after, FACTORS[word]) for before, after in changes), default=0)
        if best >= 1:
            continue
        if best >= CLOSE:
            confirm.append(f"Your resume's numbers come close to '{word}' but fall short")
        else:
            unsupported.append(f"Your resume doesn't show '{word}'")

    suggestion_tools = find_tools(suggestion)
    new_tools = suggestion_tools - find_tools(resume)
    note_tools = find_tools(evidence)
    for tool in sorted(new_tools):
        if tool in note_tools:
            confirm.append(f"{tool} is only in your note")
        else:
            unsupported.append(f"{tool} is not in your resume")

    # A tool listed only under Skills is known, not shown used. Reordering the Skills line itself
    # ("Skills: Excel, SQL") claims no use, so it isn't flagged.
    listing = bool(SKILLS_LABEL.match(suggestion))
    if not listing:
        for tool in sorted(suggestion_tools - new_tools - find_tools(used)):
            confirm.append(f"{tool} is only in your Skills list")

    for word in sorted(find_scope_words(suggestion) - find_scope_words(resume)):
        confirm.append(f"Your resume doesn't say '{word}'")

    # "Helped migrate" -> "Migrated" quietly claims the whole job.
    if len(find_help_words(resume)) > len(find_help_words(suggestion)):
        confirm.append("Your resume says you helped; this drops that")

    new_titles = find_titles(suggestion) - find_titles(resume)
    note_titles = find_titles(evidence)
    for title in sorted(new_titles):
        if title in note_titles:
            confirm.append(f"{title} is only in your note")
        else:
            unsupported.append(f"{title} is not in your resume")

    # Time units: "5 hours a week" is not "5 hours a day".
    note_units = find_time_units(evidence)
    for unit in sorted(find_time_units(suggestion) - find_time_units(resume)):
        if unit in note_units:
            confirm.append(f"{unit} is only in your note")
        else:
            unsupported.append(f"{unit} is not in your resume")

    # Outcomes are compared as a class, so honest rewording ("cutting" -> "saving") passes.
    # ponytail: an outcome reworded into a different result (source "reduced costs", suggestion
    # "increased sales") still passes; the planned meaning-level check replaces this.
    outcomes = sorted(find_outcomes(suggestion))
    if outcomes and not find_outcomes(resume):
        if find_outcomes(evidence):
            confirm.append("The result is only in your note")
        else:
            unsupported.append(f"Your resume doesn't mention a result like '{outcomes[0]}'")

    # Unknown capitalized and mixed-case names need confirmation. A sentence's first
    # ordinary capitalized word is skipped; tools, titles and acronyms are checked there too.
    resume_words = set(re.findall(r"\w+", normalize(resume) + " " + resume.casefold()))
    used_words = set(re.findall(r"\w+", normalize(used) + " " + used.casefold()))
    normalized_suggestion = normalize(suggestion)
    first_word = re.search(r"[A-Za-z][A-Za-z0-9+#]*", suggestion)
    for match in re.finditer(r"\b(?:[A-Z][A-Za-z0-9+#]*|[a-z]+[A-Z][A-Za-z0-9+#]*)", suggestion):
        word = match.group()
        if first_word and match.start() == first_word.start() and not any(c.isupper() for c in word[1:]):
            continue
        pieces = re.findall(r"\w+", normalize(word))
        # Tool claims have already been checked. Words consumed by a multiword alias
        # ("Amazon Web Services" -> "aws") must not be rechecked as unknown names.
        already_reported = (bool(find_tools(word)) or word.casefold() in new_titles
                            or (word.casefold() == "go" and "golang" in suggestion_tools)
                            or not re.search(r"(?<!\w)" + re.escape(word.casefold()) + r"(?!\w)",
                                             normalized_suggestion))
        if already_reported:
            continue
        if any(piece not in resume_words for piece in pieces):
            confirm.append(f"'{word}' isn't in your resume")
        elif not listing and any(piece not in used_words for piece in pieces):
            # Names the tool list doesn't know (C, Postman, GA4) get the same Skills check.
            confirm.append(f"'{word}' is only in your Skills list")

    # ponytail: word overlap stands in for the planned meaning-level check; replace it when that lands
    wanted = _stems(suggestion)
    if len(wanted & _stems(resume)) * 2 < len(wanted):
        confirm.append("Most of this wording isn't in your resume")

    status = "unsupported" if unsupported else "needs_confirmation" if confirm else "supported"
    return {"status": status, "reasons": unsupported + confirm}


# ponytail: whole lines stand in for whole bullets, so a bullet wrapped onto an earlier line loses
# that line's words; switch to split_resume units once they handle real PDF text (issue #22).
def _bullet_lines(bullet: str, resume_text: str) -> str:
    """The whole resume line(s) holding the bullet, so a fragment can't drop "Helped" or "Co-".
    One line is tried first; a wrapped bullet may run onto two more lines that start no new bullet."""
    lines = resume_text.splitlines()
    for size in (1, 2, 3):
        for i in range(len(lines) - size + 1):
            run = lines[i:i + size]
            if any(re.match(r"\s*[-*•–▪]\s", line) for line in run[1:]):
                continue
            if span_exists(bullet, "\n".join(run)):
                return "\n".join(run)
    return ""


def check_recommendation(rec: dict, resume_text: str) -> dict:
    """Classify one recommendation against only its own bullet and its verified resume quotes.

    A fact from another bullet never backs this one: the source is the original bullet (if it
    really is in the resume) plus the resume quotes that sit at their stated positions, each
    widened to its whole line(s), so quoting "founder" from "Co-founder" or leaving out "Helped"
    changes nothing. The model's quotes and the user's note are data, never instructions. A
    missing or wrongly typed field counts as empty, so malformed model output is never supported.
    """
    def text(value):
        return value if isinstance(value, str) else ""

    rec = rec if isinstance(rec, dict) else {}
    resume_text, bullet = text(resume_text), text(rec.get("original_bullet"))
    sources = [_bullet_lines(bullet, resume_text)] if re.search(r"\w", bullet) else []
    notes = []
    evidence = rec.get("evidence")
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        start, end = item.get("start"), item.get("end")
        if (item.get("source") == "resume" and isinstance(start, int) and isinstance(end, int)
                and 0 <= start < end <= len(resume_text) and resume_text[start:end] == item["text"]):
            # Line breaks and spaces at either end of the quote don't reach into another line.
            quote = item["text"]
            start, end = start + len(quote) - len(quote.lstrip()), end - len(quote) + len(quote.rstrip())
            if start < end:
                line_end = resume_text.find("\n", end)
                sources.append(resume_text[resume_text.rfind("\n", 0, start) + 1:
                                           line_end if line_end != -1 else len(resume_text)])
        elif item.get("source") == "evidence":
            notes.append(item["text"])
    return classify(text(rec.get("suggestion")), "\n".join(sources), "\n".join(notes))
