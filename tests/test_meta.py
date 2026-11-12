import json
from pathlib import Path

import pytest

from bangla_seo_meta import cli
from bangla_seo_meta.graphemes import grapheme_len, graphemes
from bangla_seo_meta.meta import Tag, build_meta, truncate
from bangla_seo_meta.schema import SchemaError, load_input

EXAMPLES = Path(__file__).parent.parent / "examples"
BN_TITLE = "ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়"


def all_values(result, key):
    return [dict(t.attrs).get("content") for t in result.tags if key in (dict(t.attrs).get("name"), dict(t.attrs).get("property"))]


# --- truncate ---------------------------------------------------------------

def test_truncate_leaves_short_text_alone():
    assert truncate("  Short   title ", 60) == "Short title"


def test_truncate_prefers_word_boundary():
    assert truncate("How to speed up a WordPress site today", 20) == "How to speed up a…"


def test_truncate_never_splits_a_bangla_grapheme():
    text = "ক্ষমতা " * 30
    for limit in range(2, 40):
        short = truncate(text, limit)
        assert grapheme_len(short) <= limit
        body = short[:-1]
        # every cluster of the shortened text is a cluster of the original
        assert set(graphemes(body)) <= set(graphemes(text))
        assert not body.endswith("্")


def test_truncate_falls_back_to_hard_cut_without_spaces():
    short = truncate("ক" * 50, 10)
    assert short == "ক" * 9 + "…"


def test_truncate_drops_trailing_danda_and_punctuation():
    assert truncate("প্রথম বাক্য। দ্বিতীয় বাক্যটি অনেক লম্বা", 10) == "প্রথম বাক্য…"


def test_truncate_rejects_zero():
    with pytest.raises(ValueError):
        truncate("abc", 0)


# --- build_meta -------------------------------------------------------------

def test_bangla_example_tags():
    result = build_meta(load_input(EXAMPLES / "post-bn.yaml"), site_name="Example Blog")
    assert result.get("title") == BN_TITLE
    assert result.get("canonical") == "https://example.com/wordpress-speed-up/"
    assert result.get("og:type") == "article"
    assert result.get("og:locale") == "bn_BD"
    assert result.get("og:site_name") == "Example Blog"
    assert result.get("og:image:secure_url") == "https://example.com/images/speed.webp"
    assert result.get("article:published_time") == "2026-01-10"
    assert result.get("article:author") == "https://saizul.com"
    assert all_values(result, "article:tag") == ["ওয়ার্ডপ্রেস", "গতি", "ক্যাশ"]
    assert result.get("twitter:card") == "summary_large_image"
    assert result.notes == []


def test_minimal_page_is_a_website_with_summary_card():
    result = build_meta({"title": "About us"})
    assert result.get("og:type") == "website"
    assert result.get("twitter:card") == "summary"
    assert result.get("description") is None
    assert result.get("canonical") is None
    assert all_values(result, "article:tag") == []


def test_title_is_required():
    with pytest.raises(SchemaError, match="title"):
        build_meta({"description": "No title"})


@pytest.mark.parametrize("key", ["url", "image"])
def test_relative_urls_are_rejected(key):
    with pytest.raises(SchemaError, match=key):
        build_meta({"title": "T", key: "/relative/path"})


def test_image_mapping_with_alt_text():
    result = build_meta({"title": "T", "image": {"url": "http://x.test/a.png", "alt": "একটি ছবি"}})
    assert result.get("og:image") == "http://x.test/a.png"
    assert result.get("og:image:secure_url") is None  # only for https
    assert result.get("og:image:alt") == "একটি ছবি"
    assert result.get("twitter:image:alt") == "একটি ছবি"


@pytest.mark.parametrize("language, locale", [("bn", "bn_BD"), ("en", "en_US"), ("bn-IN", "bn_IN"), ("en_gb", "en_GB"), ("xx", None)])
def test_locale_from_language(language, locale):
    assert build_meta({"title": "T", "language": language}).get("og:locale") == locale


def test_explicit_locale_wins():
    assert build_meta({"title": "T", "language": "bn", "locale": "bn-IN"}).get("og:locale") == "bn_IN"


def test_long_text_is_shortened_per_slot_with_notes():
    description = "দ্রুত " * 60
    result = build_meta({"title": "T" * 10 + " " + "শিরোনাম " * 12, "description": description})
    assert grapheme_len(result.get("title")) <= 60
    assert grapheme_len(result.get("description")) <= 155
    assert grapheme_len(result.get("og:description")) <= 200
    assert grapheme_len(result.get("og:title")) > grapheme_len(result.get("title"))
    assert any(note.startswith("description shortened") for note in result.notes)


def test_no_shorten_keeps_full_text():
    title = "শিরোনাম " * 20
    result = build_meta({"title": title}, shorten=False)
    assert result.get("title") == title.strip()
    assert result.notes == []


def test_title_template_keeps_site_name_when_shortening():
    result = build_meta({"title": "শিরোনাম " * 20}, site_name="Example Blog", title_template="{title} | {site_name}")
    title = result.get("title")
    assert title.endswith("… | Example Blog")
    assert grapheme_len(title) <= 60
    assert result.get("og:title").endswith("…")  # og:title never gets the suffix


def test_title_template_without_site_name_drops_separator():
    result = build_meta({"title": "Hello"}, title_template="{title} | {site_name}")
    assert result.get("title") == "Hello"


@pytest.mark.parametrize("template", ["{site_name}", "{title} {title}", "{nope}"])
def test_bad_title_template(template):
    with pytest.raises(SchemaError):
        build_meta({"title": "T"}, site_name="S", title_template=template)


@pytest.mark.parametrize("raw", ["example", "@example", "https://x.com/example"])
def test_twitter_handles_are_normalised(raw):
    assert build_meta({"title": "T", "twitter": {"site": raw}}).get("twitter:site") == "@example"


def test_twitter_creator_and_card_override():
    result = build_meta({"title": "T", "image": "https://x.test/i.png",
                         "twitter": {"creator": "@writer", "card": "summary"}}, twitter_site="@site")
    assert result.get("twitter:card") == "summary"
    assert result.get("twitter:creator") == "@writer"
    assert result.get("twitter:site") == "@site"


@pytest.mark.parametrize("twitter", [{"site": "not a handle"}, {"card": "player"}, "@example"])
def test_bad_twitter_input(twitter):
    with pytest.raises(SchemaError):
        build_meta({"title": "T", "twitter": twitter})


def test_comma_separated_keywords_and_robots():
    result = build_meta({"title": "T", "og_type": "article", "keywords": "seo, বাংলা ,", "robots": "noindex,  follow"})
    assert all_values(result, "article:tag") == ["seo", "বাংলা"]
    assert result.get("robots") == "noindex, follow"


def test_article_dates_are_validated():
    with pytest.raises(SchemaError, match="date_published"):
        build_meta({"title": "T", "date_published": "last week"})


def test_html_is_escaped():
    html = build_meta({"title": '<b>"Tom" & Jerry</b>', "description": 'say "hi" & <bye>'}).to_html()
    assert "<title>&lt;b&gt;\"Tom\" &amp; Jerry&lt;/b&gt;</title>" in html
    assert 'content="say &quot;hi&quot; &amp; &lt;bye&gt;"' in html
    assert "<b>" not in html


def test_tag_to_dict():
    assert Tag("meta", (("name", "x"), ("content", "y"))).to_dict() == {"element": "meta", "name": "x", "content": "y"}
    assert Tag("title", text="T").to_dict() == {"element": "title", "text": "T"}


def test_markdown_front_matter_input(tmp_path):
    post = tmp_path / "post.md"
    post.write_text("---\ntitle: বাংলা পোস্ট\nlanguage: bn\n---\nBody text.\n", encoding="utf-8")
    result = build_meta(load_input(post))
    assert result.get("og:title") == "বাংলা পোস্ট"
    assert result.get("og:locale") == "bn_BD"


# --- CLI --------------------------------------------------------------------

def test_cli_meta_html(capsys):
    code = cli.main(["meta", str(EXAMPLES / "post-bn.yaml"), "--site-name", "Example Blog",
                     "--twitter-site", "example", "--title-template", "{title} | {site_name}"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith(f"<title>{BN_TITLE} | Example Blog</title>\n")
    assert '<meta property="og:title" content="ওয়ার্ডপ্রেস' in out
    assert '<meta name="twitter:site" content="@example">' in out
    assert "application/ld+json" not in out


def test_cli_meta_with_schema(capsys):
    code = cli.main(["meta", str(EXAMPLES / "post-bn.yaml"), "--with-schema", "--article-type", "BlogPosting"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.count('<script type="application/ld+json">') == 2  # Article + FAQPage
    assert '"@type": "BlogPosting"' in out


def test_cli_meta_json(capsys):
    code = cli.main(["meta", str(EXAMPLES / "post-en.json"), "--json", "--with-schema"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["tags"][0] == {"element": "title", "text": "5 Easy Ways to Speed Up a WordPress Site"}
    assert payload["notes"] == []
    assert [s["@type"] for s in payload["schema"]] == ["Article", "FAQPage"]


def test_cli_meta_reports_shortening_on_stderr(tmp_path, capsys):
    post = tmp_path / "long.yaml"
    post.write_text("title: " + "শিরোনাম " * 20 + "\n", encoding="utf-8")
    assert cli.main(["meta", str(post)]) == 0
    captured = capsys.readouterr()
    assert "note: title shortened" in captured.err
    assert "note:" not in captured.out


def test_cli_meta_bad_input_exits_2(tmp_path, capsys):
    post = tmp_path / "bad.yaml"
    post.write_text("description: no title\n", encoding="utf-8")
    assert cli.main(["meta", str(post)]) == 2
    assert "title" in capsys.readouterr().err
    assert cli.main(["meta", str(tmp_path / "missing.yaml")]) == 2
