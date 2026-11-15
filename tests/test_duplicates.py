import json

import pytest

from bangla_seo_meta import cli
from bangla_seo_meta.batch import check_files
from bangla_seo_meta.duplicates import (
    Post,
    find_duplicates,
    issues_for,
    jaccard,
    normalise_text,
    normalise_url,
    post_slug,
    title_terms,
)

DESC = "Learn how caching, image optimisation and a CDN make your WordPress website faster in a few simple steps."


def kinds(groups):
    return sorted(g.kind for g in groups)


def write(tmp_path, name, **fields):
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()]
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# --- normalisation -----------------------------------------------------------


def test_normalise_text_folds_case_space_and_trailing_punctuation():
    assert normalise_text("  WordPress   Speed Guide! ") == "wordpress speed guide"
    assert normalise_text("ওয়ার্ডপ্রেস গাইড।") == "ওয়ার্ডপ্রেস গাইড"


def test_normalise_text_uses_nfc_for_bangla():
    composed = "\u09df"  # BENGALI LETTER YYA
    decomposed = "\u09af\u09bc"  # YA + NUKTA
    assert composed != decomposed
    assert normalise_text(composed) == normalise_text(decomposed)


@pytest.mark.parametrize(
    "a, b",
    [
        ("https://Example.com/post/", "https://example.com/post"),
        ("https://example.com/post#top", "https://example.com/post"),
        ("https://example.com:443/post", "https://example.com/post"),
        ("HTTPS://example.com/", "https://example.com"),
    ],
)
def test_normalise_url_equivalents(a, b):
    assert normalise_url(a) == normalise_url(b)


def test_normalise_url_keeps_query_path_case_and_custom_port():
    assert normalise_url("https://example.com/a?p=1") != normalise_url("https://example.com/a?p=2")
    assert normalise_url("https://example.com/A") != normalise_url("https://example.com/a")
    assert normalise_url("https://example.com:8443/a") != normalise_url("https://example.com/a")


def test_post_slug_prefers_slug_then_url_then_title():
    assert post_slug(Post("a", title="Ignored", url="https://x.test/from-url/", slug="My Slug")) == "my-slug"
    assert post_slug(Post("a", title="Ignored", url="https://x.test/blog/from-url/")) == "from-url"
    assert post_slug(Post("a", title="ওয়ার্ডপ্রেস এসইও টিপস")) == "wordpress-seo-tips"
    assert post_slug(Post("a", url="https://x.test/")) is None
    assert post_slug(Post("a")) is None


def test_title_terms_and_jaccard_ignore_stopwords():
    a = title_terms("How to speed up a WordPress site")
    b = title_terms("Speed up the WordPress site")
    assert a == b == frozenset({"speed", "wordpress", "site"})
    assert jaccard(a, b) == 1.0
    assert jaccard(frozenset(), b) == 0.0


# --- find_duplicates -----------------------------------------------------------


def test_exact_duplicates_are_grouped_per_kind():
    posts = [
        Post("a.yaml", "WordPress Speed Guide", DESC, "https://example.com/speed/", keyword="WordPress"),
        Post("b.yaml", "wordpress speed guide.", DESC, "https://example.com/speed", keyword="wordpress"),
        Post("c.yaml", "Something else entirely", "Another description", "https://example.com/other/"),
    ]
    groups = find_duplicates(posts)
    assert kinds(groups) == ["description", "keyword", "slug", "title", "url"]
    for g in groups:
        assert g.files == ["a.yaml", "b.yaml"]
    title = next(g for g in groups if g.kind == "title")
    assert title.value == "WordPress Speed Guide"  # shows the first post's original text
    assert title.level == "warning"
    assert next(g for g in groups if g.kind == "url").level == "error"


def test_slug_collision_from_titles_without_urls():
    posts = [Post("a.md", "ওয়ার্ডপ্রেস এসইও টিপস"), Post("b.md", "WordPress SEO Tips")]
    groups = find_duplicates(posts)
    slug = next(g for g in groups if g.kind == "slug")
    assert slug.value == "wordpress-seo-tips" and slug.files == ["a.md", "b.md"]


def test_similar_titles_reported_but_not_when_identical():
    posts = [
        Post("a", "WordPress site speed guide for beginners"),
        Post("b", "WordPress site speed guide for developers"),
        Post("c", "WordPress Site Speed Guide For Beginners"),
    ]
    groups = find_duplicates(posts, similar_threshold=0.6)
    similar = [g for g in groups if g.kind == "similar-title"]
    pairs = sorted(tuple(g.files) for g in similar)
    assert pairs == [("a", "b"), ("b", "c")]  # a/c are an exact duplicate instead
    assert all(0.6 <= g.similarity < 1 for g in similar)
    assert not [g for g in find_duplicates(posts, similar_threshold=1.5) if g.kind == "similar-title"]


def test_no_duplicates_for_unique_posts_or_empty_fields():
    posts = [Post("a", "First title", "", None), Post("b", "Second title", "", None), Post("c")]
    assert find_duplicates(posts) == []


def test_issues_for_names_the_other_files():
    groups = find_duplicates([Post("a", "Same"), Post("b", "same"), Post("c", "SAME")])
    issues = issues_for("b", groups)
    codes = sorted(i.code for i in issues)
    assert codes == ["duplicate-slug", "duplicate-title"]
    title = next(i for i in issues if i.code == "duplicate-title")
    assert "a, c" in title.message and title.level == "warning"
    assert issues_for("zzz", groups) == []


# --- batch / CLI ---------------------------------------------------------------


def test_check_files_attaches_cross_file_issues(tmp_path):
    a = write(tmp_path, "a.yaml", title="How to Speed Up a WordPress Website", description=DESC,
              url="https://example.com/speed/", keyword="WordPress")
    b = write(tmp_path, "b.yaml", title="How to Speed Up a WordPress Website", description=DESC,
              url="https://example.com/speed", keyword="WordPress")
    results = check_files([a, b])
    for r in results:
        codes = {i.code for i in r.report.issues}
        assert {"duplicate-url", "duplicate-slug", "duplicate-title", "duplicate-description",
                "duplicate-keyword"} <= codes
        assert not r.ok  # duplicate URL and slug are errors
    assert all(r.ok for r in check_files([a, b], duplicates=False))


def test_cli_duplicates_fail_the_batch_and_can_be_disabled(tmp_path, capsys):
    a = write(tmp_path, "a.yaml", title="How to Speed Up a WordPress Website", description=DESC,
              url="https://example.com/speed/")
    b = write(tmp_path, "b.yaml", title="Caching basics for a faster WordPress site", description=DESC + " Extra.",
              url="https://example.com/speed/")
    assert cli.main(["check", a, b]) == 1
    out = capsys.readouterr().out
    assert "Same canonical URL as" in out
    assert "Cross-file: 1 shared url, 1 shared slug." in out

    assert cli.main(["check", a, b, "--no-duplicates"]) == 0
    assert "Cross-file" not in capsys.readouterr().out


def test_cli_json_lists_duplicate_groups(tmp_path, capsys):
    a = write(tmp_path, "a.yaml", title="ওয়ার্ডপ্রেস সাইট দ্রুত করার সহজ উপায়", description=DESC)
    b = write(tmp_path, "b.yaml", title="ওয়ার্ডপ্রেস সাইট দ্রুত করার সহজ উপায়।", description=DESC + " More.")
    code = cli.main(["check", a, b, "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1  # the titles produce the same slug
    by_kind = {g["kind"]: g for g in data["duplicates"]}
    assert set(by_kind) == {"slug", "title"}
    assert by_kind["title"]["level"] == "warning" and by_kind["title"]["files"] == [a, b]
    assert "similarity" not in by_kind["title"]

    cli.main(["check", a, b, "--json", "--no-duplicates"])
    assert "duplicates" not in json.loads(capsys.readouterr().out)


def test_cli_unreadable_files_are_skipped_by_cross_checks(tmp_path, capsys):
    a = write(tmp_path, "a.yaml", title="A unique title for this post", description=DESC)
    assert cli.main(["check", a, str(tmp_path / "missing.yaml")]) == 1
    out = capsys.readouterr().out
    assert "file not found" in out and "Cross-file" not in out


def test_cli_similar_titles_threshold_validation(tmp_path, capsys):
    a = write(tmp_path, "a.yaml", title="x")
    with pytest.raises(SystemExit):
        cli.main(["check", a, "--similar-titles", "abc"])
    with pytest.raises(SystemExit):
        cli.main(["check", a, "--similar-titles", "0"])
    capsys.readouterr()
