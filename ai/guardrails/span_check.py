import re

from ai.guardrails.text import clean


def span_exists(span: str, source: str) -> bool:
    """True if span appears in source, ignoring capital letters, extra spaces and PDF punctuation.

    Whole words and whole numbers only: "led" is not in "scheduled", "c" is not in "C++",
    "js" is not in "Node.js", "3" is not in "2023", "3.6" or "3-5", "40%" is not in "140%"
    or "20-40%", "30" is not in "30%", "5" is not in "5 dozen", and "$5M" is not in "$3M-$5M".
    """
    span, source = clean(span).casefold(), clean(source).casefold()
    if not re.search(r"\w", span):
        return False  # empty or punctuation-only evidence never counts as support
    pattern = (
        r"(?<![\w$\u00a3\u20ac\u00a5])"  # not the end of a longer word or amount: "led" in "scheduled", "40" in "$40"
        r"(?<!\w\.)"      # not after a dot inside a name: "js" in "Node.js"
        r"(?<!\d[,/-])"   # not the second half of a number: "5" in "3-5", "000" in "2,000"
        + re.escape(span)
        + r"(?![\w%+#])"  # not the start of a longer word or amount: "30" in "30%", "c" in "c++"
        r"(?![.,/-]\d)"   # not the first half of a number: "3" in "3.6" or "3-5"
    )
    if re.fullmatch(r"[$\u00a3\u20ac\u00a5]?\d+(?:[.,]\d+)*(?:%|[kmbx])?\+?", span):
        # A leading decimal point, a range's first half or a spelled-out unit is part of an amount too.
        pattern = (r"(?<![.+-])" + pattern
                   + r"(?!\s*(?:[%+]|(?:percent|per cent|hundred|thousand|million|billion|dozen)\b))")
    return re.search(pattern, source) is not None
