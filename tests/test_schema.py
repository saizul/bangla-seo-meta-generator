import json
from pathlib import Path

import pytest

from bangla_seo_meta.schema import SchemaError, build_article, build_faq, load_input, to_script_tag

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_article_from_yaml_example():
    schema = build_article(load_input(EXAMPLES / "post-bn.yaml"), "BlogPosting")
    assert schema["@context"] == "https://schema.org"
    assert schema["@type"] == "BlogPosting"
    assert schema["headline"].startswith("ওয়ার্ডপ্রেস")
    assert schema["author"] == {"@type": "Person", "name": "Saizul Amin", "url": "https://saizul.com"}
    assert schema["publisher"]["logo"] == {"@type": "ImageObject", "url": "https://example.com/logo.png"}
    assert schema["datePublished"] == "2026-01-10"  # YAML parses this as a date object
    assert schema["dateModified"] == "2026-02-01T09:30:00+06:00"
    assert schema["inLanguage"] == "bn"
    assert schema["keywords"] == "ওয়ার্ডপ্রেস, গতি, ক্যাশ"


def test_faq_from_json_example():
    schema = build_faq(load_input(EXAMPLES / "post-en.json"))
    assert schema["@type"] == "FAQPage"
    question = schema["mainEntity"][0]
    assert question["@type"] == "Question"
    assert question["acceptedAnswer"] == {
        "@type": "Answer",
        "text": "Heavy themes, unoptimised images and missing page caching are the usual causes.",
    }


def test_string_author_becomes_person():
    schema = build_article({"title": "T", "url": "https://x.test/", "author": "Jane"})
    assert schema["author"] == {"@type": "Person", "name": "Jane"}


@pytest.mark.parametrize("missing", ["title", "url"])
def test_article_requires_title_and_url(missing):
    data = {"title": "T", "url": "https://x.test/"}
    del data[missing]
    with pytest.raises(SchemaError, match=missing):
        build_article(data)


def test_bad_date_is_rejected():
    with pytest.raises(SchemaError, match="date_published"):
        build_article({"title": "T", "url": "https://x.test/", "date_published": "yesterday"})


def test_faq_validation():
    with pytest.raises(SchemaError):
        build_faq({})
    with pytest.raises(SchemaError, match="item 2"):
        build_faq({"faq": [{"question": "Q", "answer": "A"}, {"question": "Q only"}]})


def test_script_tag_keeps_bangla_and_is_valid_json():
    schema = build_faq(load_input(EXAMPLES / "post-bn.yaml"))
    tag = to_script_tag(schema)
    assert tag.startswith('<script type="application/ld+json">')
    assert "ওয়ার্ডপ্রেস সাইট ধীর হয় কেন?" in tag  # not \u-escaped
    payload = tag.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert json.loads(payload) == schema


def test_script_tag_cannot_be_closed_early():
    tag = to_script_tag({"@type": "Thing", "name": "</script><b>"})
    assert tag.count("</script>") == 1
