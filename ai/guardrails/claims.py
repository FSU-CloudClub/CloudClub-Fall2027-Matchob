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


# Time units, so "5 hours a week" is not "5 hours a day". Adjective and adverb forms count too.
TIME_FORMS = {
    "millisecond": "millisecond milliseconds",
    "second": "second seconds secs",
    "minute": "minute minutes mins",
    "hour": "hour hours hourly hr hrs",
    "day": "day days daily",
    "week": "week weeks weekly wk wks",
    "month": "month months monthly",
    "quarter": "quarter quarters quarterly",
    "semester": "semester semesters",
    "year": "year years yearly annually annual yr yrs",
}
TIME = {form: name for name, forms in TIME_FORMS.items() for form in forms.split()}

# Verbs that claim a result. Bare "drive", "drove" and "lead" are left out as too ambiguous.
OUTCOME_FORMS = {
    "increase": "increase increases increased increasing",
    "improve": "improve improves improved improving",
    "reduce": "reduce reduces reduced reducing",
    "cut": "cut cuts cutting",
    "save": "save saves saved saving",
    "boost": "boost boosts boosted boosting",
    "grow": "grow grows grew grown growing",
    "raise": "raise raises raised raising",
    "lower": "lower lowers lowered lowering",
    "decrease": "decrease decreases decreased decreasing",
    "double": "double doubles doubled doubling",
    "triple": "triple triples tripled tripling",
    "quadruple": "quadruple quadruples quadrupled quadrupling",
    "accelerate": "accelerate accelerates accelerated accelerating",
    "expand": "expand expands expanded expanding",
    "generate": "generate generates generated generating",
    "achieve": "achieve achieves achieved achieving",
    "eliminate": "eliminate eliminates eliminated eliminating",
    "streamline": "streamline streamlines streamlined streamlining",
    "optimize": "optimize optimizes optimized optimizing optimise optimises optimised optimising",
    "enhance": "enhance enhances enhanced enhancing",
    "maximize": "maximize maximizes maximized maximizing maximise maximises maximised maximising",
    "minimize": "minimize minimizes minimized minimizing minimise minimises minimised minimising",
    "slash": "slash slashes slashed slashing",
    "shorten": "shorten shortens shortened shortening",
    "halve": "halve halves halved halving",
    "exceed": "exceed exceeds exceeded exceeding",
    "surpass": "surpass surpasses surpassed surpassing",
    "prevent": "prevent prevents prevented preventing",
    # The nouns "result" and "results" are left out: "showed test results" claims nothing.
    "result": "resulted resulting",
}
OUTCOME = {form: name for name, forms in OUTCOME_FORMS.items() for form in forms.split()}

# Words that say someone else did the main work. Dropping them claims the whole job.
HELP_FORMS = {
    "helped": "help helps helped helping",
    "assisted": "assist assists assisted assisting",
    "contributed": "contribute contributes contributed contributing",
    "participated": "participate participates participated participating",
}
HELP = {form: name for name, forms in HELP_FORMS.items() for form in forms.split()}


# Short forms that are units only right after a number: "5 ms", but not "an MS in Computer Science".
AFTER_NUMBER = {"ms": "millisecond", "sec": "second", "min": "minute"}


def find_time_units(text: str) -> set[str]:
    """Which time units appear, by name ("weekly" -> "week"), inside hyphenated words too
    ("hour-long", "5-day"), except the idiom "day-to-day"."""
    pieces = [p for w in _words(text) if w != "day-to-day" for p in w.split("-")]
    # "5 ms", "5-ms" and "five ms" alike.
    short = re.findall(rf"(?:\d|\b(?:{'|'.join(NUMBER_WORDS)}))[ -]?(ms|sec|min)\b", clean(text).casefold())
    return {TIME[p] for p in pieces if p in TIME} | {AFTER_NUMBER[s] for s in short}


# "Doubled as team lead" and "doubled up on shifts" name a second role or more effort, not growth.
NOT_GROWTH = re.compile(r"\bdoubl(?:ed|ing) (?:as|up)\b", re.IGNORECASE)


def find_outcomes(text: str) -> set[str]:
    """Which result verbs appear, by name ("cutting" -> "cut"). The last part of a hyphenated
    word counts ("cost-saving"), the first does not ("double-checked")."""
    words = _words(NOT_GROWTH.sub(" ", text))
    return {OUTCOME[w.split("-")[-1]] for w in words if w.split("-")[-1] in OUTCOME}


# Growth words are amounts too: "doubled" says the after number is at least twice the before.
# Bare "double" and "twice" are left out: "double major" and "presented twice" claim no growth.
MULTIPLIER_FORMS = {
    "doubled": "doubled doubling",
    "tripled": "tripled tripling",
    "quadrupled": "quadrupled quadrupling",
    "halved": "halved halving",
}
MULTIPLIER = {form: name for name, forms in MULTIPLIER_FORMS.items() for form in forms.split()}
FACTORS = {"doubled": Decimal(2), "tripled": Decimal(3), "quadrupled": Decimal(4), "halved": Decimal("0.5")}
CUT_IN_HALF = re.compile(r"\bcut(?:s|ting)?(?: [\w'-]+){0,4} in half\b")
# clean() has already turned "from 400 to 700" into "from 400-700". Words can sit between
# when the unit comes first ("from 30 minutes to 14") or the numbers are words ("from ten to twenty").
CHANGE = re.compile(rf"\bfrom ({AMOUNT})(?:-|(?: [a-z]+){{0,2}} to )({AMOUNT})(?![\w+#]|[.,]\d)")


def find_multipliers(text: str) -> set[str]:
    """Which growth words appear, by name ("doubling" -> "doubled", "cut wait times in half" ->
    "halved"). A hyphenated word stays whole, so "double-checked" claims nothing."""
    found = {MULTIPLIER[w] for w in _words(NOT_GROWTH.sub(" ", text)) if w in MULTIPLIER}
    if CUT_IN_HALF.search(clean(text).casefold()):
        found.add("halved")
    return found


def find_changes(text: str) -> list[tuple[Decimal, Decimal]]:
    """Every "from A to B" as numbers: "from 850 to 1,400 subscribers" -> (850, 1400).
    Only numbers written together count, so "6 months" elsewhere in the line is never used."""
    pairs = []
    for match in CHANGE.finditer(clean(text).casefold()):
        before, after = (Decimal(re.sub(r"[^\d.]", "", _tidy(amount))) for amount in match.groups())
        if before > 0:
            pairs.append((before, after))
    return pairs


def find_help_words(text: str) -> list[str]:
    """Every helping word, by name ("assisting" -> "assisted"), once per use, so dropping
    "Helped" from "Helped migrate help desk reports" still leaves one fewer."""
    return [HELP[w] for w in _words(text) if w in HELP]


def find_titles(text: str) -> set[str]:
    """Which job titles appear as whole words. A hyphenated title stays whole, so "co-founder"
    is a title of its own and not the same claim as "founder"."""
    return {w for w in _words(text) if w.split("-")[-1] in TITLES}


# Common tools that synonyms.json lacks. Everyday words (go, r, spring, swift, rust) are left out.
EXTRA_TOOLS = {
    "docker", "terraform", "git", "github", "github actions", "gitlab", "jenkins", "ansible",
    "flask", "django", "fastapi", "angular", "vue", "svelte", "linux", "bash", "powershell",
    "tableau", "power bi", "pandas", "numpy", "matplotlib", "jupyter", "pytest", "sqlite",
    "redis", "kafka", "spark", "hadoop", "snowflake", "jira", "figma", "cloudformation",
    "sagemaker", "bigquery", "firebase", "nginx", "helm", "kubectl", "pulumi", "ios",
    "android", "jquery", "kotlin", "salesforce", "c++", "c#",
}


def find_tools(text: str) -> set[str]:
    """Known tools and aliases, without discarding words inside a multiword alias.

    "AWS Lambda" finds both aws and lambda. Verbs and files count too ("dockerized", "Dockerfile").
    Ambiguous "go" counts as golang only after "in", "with" or "using".
    """
    # Lane 7's quantities and scope checks work before Lane 5's synonyms have merged.
    from ai.matching.normalize import SYNONYMS

    text = clean(text).casefold()
    found = set()
    for name in set(SYNONYMS) | EXTRA_TOOLS:
        aliases = [name, *SYNONYMS.get(name, [])]
        pattern = (r"(?<![\w.])(?:" + "|".join(re.escape(a) for a in aliases)
                   + r")(?:i[sz](?:e|ed|es|ing)|files?)?(?![\w+#])")
        if re.search(pattern, text):
            found.add(name)
    if re.search(r"\b(?:in|with|using)\s+go\b", text):
        found.add("golang")
    return found
