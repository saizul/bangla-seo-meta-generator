"""``bangla-seo`` command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .batch import check_files, format_summary
from .checks import ERROR, check
from .length import LIMITS, check_length
from .meta import build_meta
from .schema import SchemaError, build_article, build_faq, load_input, to_json, to_script_tag
from .translit import slugify


def _read_text(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def _cmd_length(args: argparse.Namespace) -> int:
    report = check_length(args.text, args.kind, args.min, args.max)
    print(f"{report.graphemes} graphemes ({report.codepoints} code points, {report.utf8_bytes} bytes) "
          f"- {report.status.upper()} (recommended {report.minimum}-{report.maximum})")
    return 0 if report.status == "ok" else 1


def _cmd_slug(args: argparse.Namespace) -> int:
    print(slugify(args.text, max_length=args.max_length, separator=args.separator))
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    try:
        data = load_input(args.file)
        schemas = []
        if args.type in ("article", "both"):
            schemas.append(build_article(data, args.article_type))
        if args.type in ("faq", "both"):
            schemas.append(build_faq(data))
    except (SchemaError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    render = to_script_tag if args.script_tag else to_json
    print("\n".join(render(s) for s in schemas))
    return 0


def _cmd_meta(args: argparse.Namespace) -> int:
    try:
        data = load_input(args.file)
        result = build_meta(data, site_name=args.site_name, twitter_site=args.twitter_site,
                            title_template=args.title_template, shorten=not args.no_shorten)
        schemas = []
        if args.with_schema:
            schemas.append(build_article(data, args.article_type))
            if data.get("faq"):
                schemas.append(build_faq(data))
    except (SchemaError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        payload = result.to_dict()
        if schemas:
            payload["schema"] = schemas
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result.to_html())
        for schema in schemas:
            print(to_script_tag(schema))
        for note in result.notes:
            print(f"note: {note}", file=sys.stderr)
    return 0


def _cmd_check_files(args: argparse.Namespace) -> int:
    if any(v for v in (args.title, args.description, args.keyword, args.body_file)):
        print("error: --title/--description/--keyword/--body-file cannot be combined with FILE arguments", file=sys.stderr)
        return 2
    results = check_files(args.files)
    if args.json:
        print(json.dumps({"ok": all(r.ok for r in results), "files": [r.to_dict() for r in results]},
                         ensure_ascii=False, indent=2))
    else:
        for r in results:
            if not r.error and not r.report.issues:
                continue
            print(f"{r.path}:")
            if r.error:
                print(f"  [ERROR  ] {r.error}")
            else:
                for issue in r.report.issues:
                    print(f"  [{issue.level.upper():7}] {issue.message}")
        print()
        print(format_summary(results))
    return 0 if all(r.ok for r in results) else 1


def _cmd_check(args: argparse.Namespace) -> int:
    if args.files:
        return _cmd_check_files(args)
    body = _read_text(args.body_file) if args.body_file else None
    report = check(args.title, args.description, args.keyword, body)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        if report.title_graphemes is not None:
            print(f"Title:       {report.title_graphemes} graphemes")
        if report.description_graphemes is not None:
            print(f"Description: {report.description_graphemes} graphemes")
        if report.readability:
            r = report.readability
            print(f"Body:        {r.words} words, {r.sentences} sentences, "
                  f"avg {r.avg_sentence_words} words/sentence, ~{r.reading_minutes} min read")
            if r.keyword_density is not None:
                line = f"Keyword density: {r.keyword_density}%"
                if r.keyword_density_content is not None:
                    line += f" of all words, {r.keyword_density_content}% of {r.content_words} content words (stopwords removed)"
                print(line)
            if r.top_terms:
                print("Top terms:   " + ", ".join(f"{t.term} ({t.count})" for t in r.top_terms))
        for issue in report.issues:
            print(f"[{issue.level.upper():7}] {issue.message}")
        if not report.issues:
            print("No issues found.")
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bangla-seo", description="SEO metadata helpers for Bangla and English posts.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("length", help="grapheme-aware length check")
    p.add_argument("text")
    p.add_argument("--kind", choices=sorted(LIMITS), default="title")
    p.add_argument("--min", type=int, help="override the recommended minimum")
    p.add_argument("--max", type=int, help="override the recommended maximum")
    p.set_defaults(func=_cmd_length)

    p = sub.add_parser("slug", help="make a URL slug (Bangla is transliterated)")
    p.add_argument("text")
    p.add_argument("--max-length", type=int, default=60)
    p.add_argument("--separator", default="-")
    p.set_defaults(func=_cmd_slug)

    p = sub.add_parser("schema", help="generate Article / FAQPage JSON-LD from a YAML or JSON file")
    p.add_argument("file")
    p.add_argument("--type", choices=["article", "faq", "both"], default="both")
    p.add_argument("--article-type", default="Article", help="e.g. BlogPosting or NewsArticle")
    p.add_argument("--script-tag", action="store_true", help='wrap output in <script type="application/ld+json">')
    p.set_defaults(func=_cmd_schema)

    p = sub.add_parser("meta", help="generate <title>, description, canonical, Open Graph and Twitter card tags")
    p.add_argument("file", help="YAML, JSON or Markdown (front matter) post file")
    p.add_argument("--site-name", help="og:site_name (overrides site_name in the file)")
    p.add_argument("--twitter-site", help="twitter:site handle, e.g. @example (overrides twitter.site)")
    p.add_argument("--title-template", help='format for the <title> element, e.g. "{title} | {site_name}"')
    p.add_argument("--no-shorten", action="store_true", help="keep long titles and descriptions as they are")
    p.add_argument("--with-schema", action="store_true", help="also emit Article (and FAQPage when faq is set) JSON-LD")
    p.add_argument("--article-type", default="Article", help="schema type used with --with-schema")
    p.add_argument("--json", action="store_true", help="print the tags as JSON instead of HTML")
    p.set_defaults(func=_cmd_meta)

    p = sub.add_parser("check", help="report title/description issues, keyword presence and readability hints")
    p.add_argument("files", nargs="*", metavar="FILE",
                   help="YAML/JSON post files or glob patterns (title, description, keyword, body or body_file); "
                        "prints a summary table and exits 1 if any file has errors")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--keyword")
    p.add_argument("--body-file", help="plain-text article body ('-' for stdin)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_check)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
