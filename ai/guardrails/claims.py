"""Find the claims in a sentence that the guardrail checks against the resume."""

import re
from decimal import Decimal, localcontext

from ai.guardrails.text import clean

# Number words are amounts too: "a team of ten" claims 10.
NUMBER_WORDS = {
    "zero": 0, "one": 1,
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "dozen": 12,
}

SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000, "billion": 1000000000,
          "k": 1000, "m": 1000000, "b": 1000000000, "dozen": 12}
VAGUE_AMOUNTS = {"dozens", "hundreds", "thousands", "millions", "billions"}
ONES = "one|two|three|four|five|six|seven|eight|nine"
TENS = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
SMALL = "|".join(w for w, n in NUMBER_WORDS.items() if n < 20 or w == "dozen")
UNDER_100 = rf"(?:(?:{TENS})(?:[- ](?:{ONES}))?|(?:{SMALL}))"
UNDER_1000 = rf"(?:(?:{ONES}) hundred(?: (?:and )?{UNDER_100})?|{UNDER_100})"
WORD_NUMBER = (rf"(?:{UNDER_1000}(?: (?:billion|million|thousand)"
               rf"(?: (?:and )?{UNDER_1000})?)*|hundred|thousand|million|billion)")
DIGIT_NUMBER = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
UNIT = r"percent|per cent|hundred|thousand|million|billion|dozen|[%kmbx]"
CURRENCY = "$\u00a3\u20ac\u00a5"  # dollar, pound, euro, yen
# A trailing "+" is part of the claim: "500+ users" says at least 500.
AMOUNT = (rf"(?:[+-]?[{CURRENCY}]?|[{CURRENCY}][+-]?)(?:{DIGIT_NUMBER}|{WORD_NUMBER})"
          rf"(?: ?(?:{UNIT}))?(?: ?\+)?")
ORDINAL = r"\d+(?:st|nd|rd|th)"
NUMBER_PATTERN = re.compile(
    rf"(?<![\w.{CURRENCY}])(?:(?P<between>between) )?"
    rf"(?P<first>{ORDINAL}|{AMOUNT}|{'|'.join(sorted(VAGUE_AMOUNTS))})"
    rf"(?:\s*(?(between)and|(?:-|to|through))\s*(?P<last>{ORDINAL}|{AMOUNT}))?(?![\w+#]|[.,]\d)"
)

# Verbs that claim more responsibility than "helped" or "worked on". Every form maps to one
# name, so "leading" and "led" are the same claim. Bare "design", "direct" and "own" are left
# out because as nouns and adjectives they are everyday words.
SCOPE_FORMS = {
    "led": "lead leads leading led",
    "managed": "manage manages managing managed",
    "owned": "owns owning owned",
    "architected": "architects architecting architected",
    "designed": "designs designing designed",
    "spearheaded": "spearhead spearheads spearheading spearheaded",
    "directed": "directs directing directed",
    "founded": "founds founded founding",
    "oversaw": "oversee oversees overseeing oversaw overseen",
    "headed": "heads headed heading",
    "supervised": "supervise supervises supervising supervised",
    "chaired": "chairs chaired chairing",
}
SCOPE = {form: name for name, forms in SCOPE_FORMS.items() for form in forms.split()}

# Job titles. Singular only: "worked with engineers" names other people, not the user's title.
TITLES = {
    "intern", "engineer", "developer", "programmer", "analyst", "scientist", "manager",
    "supervisor", "director", "coordinator", "specialist", "consultant", "administrator",
    "technician", "architect", "president", "founder", "officer", "executive",
}


def find_numbers(text: str) -> list[str]:
    """Amounts in text order: "40 percent" -> "40%", "$5M" -> "$5000000", "ten" -> "10".

    A range is one amount, so "40%" is not backed by "20-40%". A digit stuck to letters
    is part of a name, not a number: S3, EC2, Python3. "500+" and places like "1st" are
    amounts too, and so are place ranges ("1st-3rd"). A lone "one" is not ("one of the
    first", "one-click").
    """
    amounts = []
    for match in NUMBER_PATTERN.finditer(clean(text).casefold()):
        if match.group() == "one":
            continue
        first, last = match["first"], match["last"]
        if last is not None:
            # A magnitude written once covers both ends: "3-5k" is "3k-5k", "3-5 dozen" is 36-60,
            # "two to three hundred thousand" is 200000-300000.
            scale = re.search(r"(?<=[\d ])((?:hundred|thousand|million|billion)"
                              r"(?: (?:hundred|thousand|million|billion))*|dozen|[kmb])(?: ?\+)?$", last)
            if scale and re.fullmatch(rf"[{CURRENCY}]?(?:[\d.,]+|{UNDER_100}|(?:{ONES}) hundred)", first):
                # "two hundred to three hundred thousand" already has its hundred; add the thousand.
                words = scale.group(1).split()
                if first.endswith(" hundred") and words[0] == "hundred":
                    words = words[1:]
                first = " ".join([first, *words])
            first, last = _tidy(first), _tidy(last)
            # "20% to 40%" and "20-40%" describe the same range, as do "$3-$5" and "$3-5".
            if first.endswith("%") and last.endswith("%"):
                first = first[:-1]
            if first[:1] in CURRENCY and last[:1] == first[:1]:
                last = last[1:]
            first += "-" + last
        else:
            first = _tidy(first)
        amounts.append(first)
    return amounts


def _tidy(amount: str) -> str:
    """Canonical value while keeping currency, percent and multiplication units distinct."""
    if amount in VAGUE_AMOUNTS or re.fullmatch(ORDINAL, amount):
        return amount
    plus = "+" if amount.endswith("+") else ""
    currency = next((c for c in CURRENCY if c in amount), "")
    body = re.sub(rf"[{CURRENCY}]| ?\+$", "", amount)
    sign = -1 if body.startswith("-") else 1
    # Greedily parse the complete word number before considering an extra unit.
    # In "one thousand five hundred", hundred belongs to the number, not a multiplier.
    match = re.fullmatch(rf"({DIGIT_NUMBER}|{WORD_NUMBER})((?: ?(?:{UNIT}))*)", body.lstrip("+-"))
    number, units = match[1], re.findall(UNIT, match[2])  # "3 hundred thousand" has two
    if re.search(r"\d", number):
        value = Decimal(number.replace(",", ""))
    else:
        total, group = 0, 0
        for word in re.findall(r"[a-z]+", number):
            if word in NUMBER_WORDS:
                group += NUMBER_WORDS[word]
            elif word == "hundred":
                group = (group or 1) * 100
            elif word in SCALES:
                total += (group or 1) * SCALES[word]
                group = 0
        value = Decimal(total + group)
    scale = 1
    for unit in units:
        scale *= SCALES.get(unit, 1)
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits) + len(str(scale)) + 2)
        value *= sign * scale
    digits = format(value, "f")
    if "." in digits:
        digits = digits.rstrip("0").rstrip(".")
    suffix = "%" if {"%", "percent", "per cent"} & set(units) else "x" if "x" in units else ""
    return currency + digits + suffix + plus


def _words(text: str) -> list[str]:
    """Lowercase words; a hyphenated word stays whole, so "co-led" is not "led"."""
    return re.findall(r"\w+(?:-\w+)*", clean(text).casefold())


def find_scope_words(text: str) -> set[str]:
    """Which responsibility verbs appear, by name ("leading" -> "led"). Whole words only."""
    return {SCOPE[w] for w in _words(text) if w in SCOPE}


def find_titles(text: str) -> set[str]:
    """Which job titles appear as whole words. A hyphenated title stays whole, so "co-founder"
    is a title of its own and not the same claim as "founder"."""
    return {w for w in _words(text) if w.split("-")[-1] in TITLES}
