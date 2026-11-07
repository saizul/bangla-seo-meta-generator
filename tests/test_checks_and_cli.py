import json
from pathlib import Path

from bangla_seo_meta import cli
from bangla_seo_meta.checks import analyze_readability, check, split_words

EXAMPLES = Path(__file__).parent.parent / "examples"
BODY_BN = (EXAMPLES / "body-bn.txt").read_text(encoding="utf-8")


def codes(report):
    return {issue.code for issue in report.issues}


def test_clean_english_metadata():
    report = check(
        title="How to Speed Up a WordPress Website in 2026",
        description="Learn how caching, image optimisation and a CDN make your WordPress website faster in a few simple steps.",
        keyword="WordPress",
    )
    assert report.ok
    assert report.issues == []


def test_long_title_and_missing_keyword():
    report = check(title="x" * 80, description="short", keyword="wordpress")
    assert {"title-long", "description-short", "keyword-missing-title", "keyword-missing-description"} <= codes(report)
    assert report.ok  # warnings only


def test_empty_title_is_an_error():
    report = check(title="  ")
    assert "title-empty" in codes(report)
    assert not report.ok


def test_bangla_keyword_in_inflected_form_is_found():
    report = check(title="ওয়ার্ডপ্রেসের গতি বাড়ানোর উপায়", keyword="ওয়ার্ডপ্রেস")
    assert "keyword-missing-title" not in codes(report)


def test_bangla_keyword_not_matched_inside_a_conjunct():
    report = check(title="ক্ষমা চাওয়ার সহজ উপায়", keyword="ক")
    assert "keyword-missing-title" in codes(report)


def test_identical_title_and_description():
    assert "title-equals-description" in codes(check(title="Same text here for both", description="same text   here for both"))


def test_split_words_keeps_bangla_words_whole():
    assert split_words("আমি বাংলায় গান গাই।") == ["আমি", "বাংলায়", "গান", "গাই"]


def test_readability_bangla_sentences_use_danda():
    stats = analyze_readability(BODY_BN, keyword="ক্যাশ")
    assert stats.sentences == 4
    assert stats.words == len(split_words(BODY_BN))
    assert stats.keyword_density == round(100 / stats.words, 2)


def test_readability_hints():
    long_sentence = " ".join(["word"] * 40) + "."
    report = check(body=long_sentence)
    assert {"long-sentences", "thin-content"} <= codes(report)


def test_keyword_stuffing():
    report = check(body=("seo " * 50) + ("filler " * 100), keyword="seo")
    assert "keyword-stuffing" in codes(report)


def test_cli_slug(capsys):
    assert cli.main(["slug", "ওয়ার্ডপ্রেস এসইও গাইড"]) == 0
    assert capsys.readouterr().out.strip() == "wordpress-seo-guide"


def test_cli_length_exit_codes(capsys):
    assert cli.main(["length", "বাংলা"]) == 1  # 2 graphemes: too short
    assert "2 graphemes (5 code points" in capsys.readouterr().out
    assert cli.main(["length", "How to Speed Up a WordPress Website in 2026"]) == 0


def test_cli_schema_both(capsys):
    assert cli.main(["schema", str(EXAMPLES / "post-bn.yaml")]) == 0
    out = capsys.readouterr().out
    assert '"@type": "Article"' in out and '"@type": "FAQPage"' in out


def test_cli_schema_article_type(capsys):
    assert cli.main(["schema", str(EXAMPLES / "post-en.json"), "--type", "article", "--article-type", "BlogPosting"]) == 0
    assert '"@type": "BlogPosting"' in capsys.readouterr().out


def test_cli_schema_error(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("title: only a title\n", encoding="utf-8")
    assert cli.main(["schema", str(bad), "--type", "faq"]) == 2
    assert "faq" in capsys.readouterr().err


def test_cli_check_json(capsys):
    code = cli.main(["check", "--title", "x" * 80, "--keyword", "seo", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0 and data["ok"] is True
    assert data["title_graphemes"] == 80
