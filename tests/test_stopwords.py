import json

from bangla_seo_meta import cli
from bangla_seo_meta.checks import analyze_readability, check
from bangla_seo_meta.stopwords import content_words, is_stopword

BODY = "ওয়ার্ডপ্রেস সাইট ধীর হলে দর্শক চলে যায়। তাই গতি বাড়ানো জরুরি। ওয়ার্ডপ্রেস এর জন্য ক্যাশ ব্যবহার করুন।"


def test_is_stopword_bangla_english_and_case():
    assert is_stopword("এবং") and is_stopword("জন্য")
    assert is_stopword("The") and is_stopword("OF")
    assert not is_stopword("ওয়ার্ডপ্রেস") and not is_stopword("WordPress")


def test_is_stopword_extra_words():
    assert not is_stopword("সাইট")
    assert is_stopword("সাইট", extra=["সাইট"])


def test_content_words_drops_stopwords_and_numbers():
    words = ["The", "fast", "WordPress", "of", "2026", "এবং", "ক্যাশ"]
    assert content_words(words) == ["fast", "WordPress", "ক্যাশ"]


def test_content_words_keeps_keyword_even_if_it_is_a_stopword():
    assert content_words(["the", "one", "plugin"], keep=["one"]) == ["one", "plugin"]


def test_readability_content_words_and_density():
    stats = analyze_readability(BODY, keyword="ওয়ার্ডপ্রেস")
    assert 0 < stats.content_words < stats.words
    assert stats.keyword_density == round(2 * 100 / stats.words, 2)
    assert stats.keyword_density_content == round(2 * 100 / stats.content_words, 2)
    assert stats.keyword_density_content > stats.keyword_density


def test_top_terms_ranked_and_only_repeated_words():
    stats = analyze_readability("Cache the cache and the CDN; a CDN helps the cache. Images load.")
    assert [(t.term, t.count) for t in stats.top_terms] == [("cache", 3), ("cdn", 2)]


def test_no_keyword_means_no_density_but_terms_still_listed():
    stats = analyze_readability("speed speed speed matters")
    assert stats.keyword_density is None and stats.keyword_density_content is None
    assert stats.top_terms[0].term == "speed"


def test_keyword_is_kept_in_content_words_even_when_it_is_a_stopword():
    stats = analyze_readability("and the of to", keyword="and")
    assert stats.content_words == 1 and stats.keyword_density_content == 100.0
    assert analyze_readability("2026 2027", keyword="2026").keyword_density_content == 100.0


def test_stuffing_warning_still_uses_all_word_density():
    report = check(body=("seo " * 50) + ("filler " * 100), keyword="seo")
    assert "keyword-stuffing" in {i.code for i in report.issues}
    assert report.readability.keyword_density == 33.33
    assert report.readability.keyword_density_content == 33.33


def test_cli_text_and_json_output(tmp_path, capsys):
    body = tmp_path / "body.txt"
    body.write_text(BODY, encoding="utf-8")
    cli.main(["check", "--keyword", "ওয়ার্ডপ্রেস", "--body-file", str(body)])
    out = capsys.readouterr().out
    assert "content words (stopwords removed)" in out
    assert "Top terms:   ওয়ার্ডপ্রেস (2)" in out
    cli.main(["check", "--keyword", "ওয়ার্ডপ্রেস", "--body-file", str(body), "--json"])
    data = json.loads(capsys.readouterr().out)["readability"]
    assert data["top_terms"][0] == {"term": "ওয়ার্ডপ্রেস", "count": 2}
    assert data["content_words"] > 0 and data["keyword_density_content"] is not None
