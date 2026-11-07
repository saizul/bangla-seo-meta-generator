import pytest

from bangla_seo_meta.graphemes import boundaries, count_term, grapheme_len, graphemes


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", 0),
        ("hello", 5),
        ("আমি", 2),  # আ + মি (vowel sign i)
        ("বাংলা", 2),  # বাং + লা: aa-kar and anusvara attach to their consonant
        ("ক্ষ", 1),  # conjunct via hasanta
        ("ক্ষমা", 2),
        ("বাংলাদেশ", 4),
        ("সংখ্যা", 2),
        ("কি করছেন?", 7),
        ("é", 1),  # latin e + combining acute
        ("a\r\nb", 3),
        ("👨‍👩‍👧", 1),  # emoji ZWJ family
        ("🇧🇩", 1),  # flag
    ],
)
def test_grapheme_len(text, expected):
    assert grapheme_len(text) == expected


def test_codepoints_differ_from_graphemes():
    assert len("বাংলা") == 5
    assert grapheme_len("বাংলা") == 2


def test_clusters_are_returned_in_order():
    assert graphemes("বাংলা") == ["বাং", "লা"]
    assert graphemes("ক্ষমা") == ["ক্ষ", "মা"]


def test_zwj_after_hasanta_keeps_the_conjunct_together():
    assert grapheme_len("র্‍য") == 1


def test_boundaries():
    assert boundaries("বাংলা") == {0, 3, 5}


def test_count_term_strict_respects_grapheme_boundaries():
    assert count_term("কথা বলি", "কথা", strict=True) == 1
    assert count_term("কথা বলি", "কথ", strict=True) == 0  # would split the aa-kar from its consonant


def test_count_term_never_matches_inside_a_conjunct():
    assert count_term("ক্ষমা", "ক") == 0
    assert count_term("ক্ষমা", "ক", strict=True) == 0


def test_count_term_is_case_insensitive_and_counts_all():
    assert count_term("WordPress and wordpress", "WORDPRESS") == 2
    assert count_term("anything", "") == 0


def test_count_term_matches_inflected_bangla_unless_strict():
    assert count_term("ওয়ার্ডপ্রেসের গতি", "ওয়ার্ডপ্রেস") == 1
    assert count_term("ওয়ার্ডপ্রেসের গতি", "ওয়ার্ডপ্রেস", strict=True) == 0
