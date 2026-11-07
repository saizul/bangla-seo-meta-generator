import pytest

from bangla_seo_meta.length import check_length


def test_english_title_ok():
    report = check_length("How to Speed Up a WordPress Website in 2026")
    assert report.status == "ok"
    assert report.graphemes == report.codepoints == 43
    assert report.remaining == 17


def test_english_title_too_long():
    assert check_length("x" * 61).status == "long"
    assert check_length("x" * 60).status == "ok"


def test_short_and_empty():
    assert check_length("Hi").status == "short"
    assert check_length("   ").status == "empty"


def test_bangla_counts_graphemes_not_codepoints():
    # 42 code points but 27 graphemes: conjuncts and vowel signs fold into their consonant.
    title = "ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়"
    report = check_length(title)
    assert report.graphemes < report.codepoints
    assert report.utf8_bytes > report.codepoints
    assert report.graphemes == 27


def test_whitespace_is_normalised():
    assert check_length("a   b\n c").text == "a b c"


def test_description_limits_and_overrides():
    text = "word " * 31  # 154 chars once stripped
    assert check_length(text, "description").status == "ok"
    assert check_length(text, "description", maximum=100).status == "long"


def test_unknown_kind():
    with pytest.raises(ValueError):
        check_length("x", "slug")
