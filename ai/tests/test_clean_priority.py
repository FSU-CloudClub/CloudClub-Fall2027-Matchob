import pytest

from ai.extraction.clean import clean_posting
from ai.extraction.priority import priority

def test_priority():
    assert priority("Experience with Go is a plus") == "nice"
    assert priority("Preferred: AWS") == "nice"
    assert priority("Must have: Python") == "must"
    
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_clean_posting(newline):
    posting = newline.join([
        "About us",
        "We build software for cafés.",
        "",
        "We work around the world.",
        "Requirements:",
        "  Must have: Python  ",
        "Experience with Go is a plus",
        "",
        "Benefits:",
        "Health insurance and paid leave.",
        "",
        "Free lunches.",
        "Preferred qualifications:",
        "\tPreferred: AWS",
    ])

    cleaned_posting = clean_posting(posting)

    assert [line["text"] for line in cleaned_posting] == [
        "Requirements:",
        "Must have: Python",
        "Experience with Go is a plus",
        "Preferred qualifications:",
        "Preferred: AWS",
    ]
    for line in cleaned_posting:
        assert posting[line["start"]:line["end"]] == line["text"]
