"""One text cleanup that every guardrail check runs first, so PDF quirks never decide a label."""

import re
import unicodedata

# Curly quotes become straight, PDF dashes and minus signs become "-",
# and invisible characters (soft hyphen, zero-width spaces) are removed.
_PLAIN = str.maketrans(
    "\u2018\u2019\u201c\u201d\u2010\u2011\u2012\u2013\u2014\u2015\u2212",
    "''\"\"-------",
    "\u00ad\u200b\u200c\u200d\ufeff",
)

# Spelled-out amounts can end in "plus" too: "five-plus years", "$5 million-plus".
_NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                 "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
                 "seventy|eighty|ninety|hundred|thousand|million|billion|dozen")


def clean(text: str) -> str:
    """Plain characters and single spaces (tabs, line breaks and no-break spaces too). Case is kept.

    Digit ranges lose their inner spaces; "20 to 40%" becomes "20-40%" and "3k to 5k" "3k-5k".
    "$ 5,000" becomes "$5,000". "500-plus", "500 plus", "500 +" and "five-plus" end in "+";
    "plus-size" is left alone.
    """
    text = " ".join(unicodedata.normalize("NFKC", text).translate(_PLAIN).split())
    text = re.sub(r"([$\u00a3\u20ac\u00a5]) (?=\d)", r"\1", text)  # "$ 5,000" is "$5,000"
    text = re.sub(r"(\d[%kmb]?|\b(?:" + _NUMBER_WORDS + r"))(?: \+|[- ]plus(?![\w-]))", r"\1+",
                  text, flags=re.IGNORECASE)
    text = re.sub(r"\bbetween (\$?\d+(?:[.,]\d+)*%?) and (\$?\d+(?:[.,]\d+)*%?)\b",
                  r"\1-\2", text, flags=re.IGNORECASE)
    # "3k to 5k" and "$3M to $5M" are ranges too.
    return re.sub(r"(?:(?<=[\d%])|(?<=\d[kmb]))\s*(?:-|to|through)\s*(?=[$\u00a3\u20ac\u00a5]?(?:\d|\.\d))",
                  "-", text, flags=re.IGNORECASE)
