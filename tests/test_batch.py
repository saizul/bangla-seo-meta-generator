import json

from bangla_seo_meta import cli
from bangla_seo_meta.batch import check_file, check_files, expand_paths, format_summary

GOOD = """title: How to Speed Up a WordPress Website in 2026
description: Learn how caching, image optimisation and a CDN make your WordPress website faster in a few simple steps.
keywords: [WordPress, speed]
"""
BAD = "title: '   '\ndescription: short\n"


def make(tmp_path):
    (tmp_path / "good.yaml").write_text(GOOD, encoding="utf-8")
    (tmp_path / "bad.yaml").write_text(BAD, encoding="utf-8")
    return tmp_path


def test_expand_paths_globs_sorts_and_dedupes(tmp_path):
    make(tmp_path)
    (tmp_path / "sub").mkdir()
    pattern = str(tmp_path / "*.yaml")
    out = expand_paths([pattern, str(tmp_path / "good.yaml")])
    assert out == [str(tmp_path / "bad.yaml"), str(tmp_path / "good.yaml")]


def test_expand_paths_keeps_unmatched_for_error_reporting(tmp_path):
    assert expand_paths([str(tmp_path / "nope-*.yaml")]) == [str(tmp_path / "nope-*.yaml")]


def test_check_file_ok_and_error(tmp_path):
    make(tmp_path)
    good = check_file(str(tmp_path / "good.yaml"))
    assert good.ok and good.errors == 0
    bad = check_file(str(tmp_path / "bad.yaml"))
    assert not bad.ok and bad.errors == 1 and bad.warnings >= 1


def test_check_file_reads_body_file(tmp_path):
    (tmp_path / "body.txt").write_text("word " * 50, encoding="utf-8")
    (tmp_path / "p.yaml").write_text(GOOD + "body_file: body.txt\n", encoding="utf-8")
    result = check_file(str(tmp_path / "p.yaml"))
    assert result.report.readability.words == 50


def test_check_file_unreadable_inputs(tmp_path):
    assert check_file(str(tmp_path / "missing.yaml")).error == "file not found"
    (tmp_path / "list.yaml").write_text("- a\n- b\n", encoding="utf-8")
    assert "mapping" in check_file(str(tmp_path / "list.yaml")).error
    (tmp_path / "broken.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    broken = check_file(str(tmp_path / "broken.yaml"))
    assert broken.error and not broken.ok


def test_format_summary_has_table_and_totals(tmp_path):
    make(tmp_path)
    text = format_summary(check_files([str(tmp_path / "*.yaml")]))
    lines = text.splitlines()
    assert lines[0].split() == ["File", "Errors", "Warnings", "Status"]
    assert "FAIL" in text and "ok" in text
    assert lines[-1].startswith("2 file(s) checked, 1 with errors")


def test_cli_batch_exit_nonzero_when_any_error(tmp_path, capsys):
    make(tmp_path)
    code = cli.main(["check", str(tmp_path / "good.yaml"), str(tmp_path / "bad.yaml")])
    out = capsys.readouterr().out
    assert code == 1
    assert "2 file(s) checked, 1 with errors" in out
    assert "Title is empty" in out or "title" in out.lower()


def test_cli_batch_all_good_exits_zero(tmp_path, capsys):
    make(tmp_path)
    assert cli.main(["check", str(tmp_path / "good.yaml")]) == 0
    assert "1 file(s) checked, 0 with errors" in capsys.readouterr().out


def test_cli_batch_glob_and_json(tmp_path, capsys):
    make(tmp_path)
    code = cli.main(["check", str(tmp_path / "*.yaml"), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1 and data["ok"] is False
    assert [f["ok"] for f in data["files"]] == [False, True]


def test_cli_batch_missing_file_is_an_error(tmp_path, capsys):
    assert cli.main(["check", str(tmp_path / "nope.yaml")]) == 1
    assert "file not found" in capsys.readouterr().out


def test_cli_rejects_mixing_files_and_flags(tmp_path, capsys):
    make(tmp_path)
    assert cli.main(["check", str(tmp_path / "good.yaml"), "--title", "x"]) == 2
    assert "cannot be combined" in capsys.readouterr().err


MD_POST = """---
title: How to Speed Up a WordPress Website in 2026
description: Learn how caching, image optimisation and a CDN make your WordPress website faster in a few simple steps.
keywords: [WordPress, speed]
---

WordPress speed matters. Caching helps a lot.
"""


def test_markdown_front_matter_is_checked_with_body(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(MD_POST, encoding="utf-8")
    result = check_file(str(path))
    assert result.error is None and result.ok
    assert result.report.readability is not None
    assert result.report.readability.words >= 6


def test_markdown_glob_and_json_output(tmp_path, capsys):
    (tmp_path / "a.md").write_text(MD_POST, encoding="utf-8")
    assert cli.main(["check", str(tmp_path / "*.md"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_markdown_front_matter_body_overrides_text(tmp_path):
    from bangla_seo_meta.schema import load_input
    path = tmp_path / "p.markdown"
    path.write_text("---\ntitle: T\nbody: inline body\n---\nignored text\n", encoding="utf-8")
    assert load_input(path)["body"] == "inline body"


def test_markdown_without_front_matter_is_an_error(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("# Just a heading\n", encoding="utf-8")
    result = check_file(str(path))
    assert result.error and "front matter" in result.error and not result.ok


def test_markdown_unterminated_front_matter_is_an_error(tmp_path):
    path = tmp_path / "broken.md"
    path.write_text("---\ntitle: T\n", encoding="utf-8")
    result = check_file(str(path))
    assert result.error and "unterminated" in result.error


def test_schema_command_reads_markdown(tmp_path, capsys):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: Hello\nurl: https://example.com/hello/\n---\nBody\n", encoding="utf-8")
    assert cli.main(["schema", str(path), "--type", "article"]) == 0
    assert json.loads(capsys.readouterr().out)["headline"] == "Hello"
