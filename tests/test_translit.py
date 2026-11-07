import pytest

from bangla_seo_meta.translit import phonetic, slugify, transliterate, transliterate_word


@pytest.mark.parametrize(
    "bangla, latin",
    [
        ("বাংলা", "bangla"),
        ("আমি", "ami"),
        ("আমার", "amar"),
        ("বই", "boi"),
        ("কলম", "kolom"),
        ("মানুষ", "manush"),
        ("গান", "gan"),
        ("সত্য", "sotto"),  # ya-phala doubles
        ("সুন্দর", "sundor"),  # hasanta suppresses the inherent vowel
        ("স্কুল", "skul"),
        ("শিক্ষা", "shikkha"),
        ("বাংলাদেশ", "bangladesh"),
        ("ঢাকা", "dhaka"),
        ("পড়া", "pora"),  # ড় -> r
        ("বাড়ি", "bari"),
        ("বাংলায়", "banglay"),  # য় -> y
        ("২০২৬", "2026"),
    ],
)
def test_phonetic_words(bangla, latin):
    assert transliterate_word(bangla) == latin


def test_loanword_dictionary_and_suffix():
    assert transliterate_word("ওয়ার্ডপ্রেস") == "wordpress"
    assert transliterate_word("এসইও") == "seo"
    assert transliterate_word("ওয়ার্ডপ্রেসের") == "wordpresser"


def test_decomposed_input_gives_same_result():
    composed = "পড়া"
    decomposed = "পড়া"
    assert phonetic(decomposed) == phonetic(composed)


def test_transliterate_leaves_other_text_alone():
    assert transliterate("SEO গাইড 2026!") == "SEO guide 2026!"


def test_slug_bangla():
    assert slugify("ওয়ার্ডপ্রেস এসইও টিপস ২০২৬") == "wordpress-seo-tips-2026"
    assert slugify("আমি বাংলায় গান গাই।") == "ami-banglay-gan-gai"


def test_slug_english_passes_through():
    assert slugify("Hello, World! It's 2026") == "hello-world-it-s-2026"
    assert slugify("Café Déjà Vu") == "cafe-deja-vu"


def test_slug_mixed():
    assert slugify("ওয়ার্ডপ্রেস Speed Guide") == "wordpress-speed-guide"


def test_slug_truncates_on_word_boundary():
    assert slugify("one two three four", max_length=12) == "one-two"
    assert slugify("one two three four", max_length=13) == "one-two-three"


def test_slug_custom_separator_and_empty():
    assert slugify("a b c", separator="_") == "a_b_c"
    assert slugify("!!!") == ""
