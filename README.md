# bangla-seo-meta-generator

[![CI](https://github.com/saizul/bangla-seo-meta-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/bangla-seo-meta-generator/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white) ![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

A small Python library and CLI for writing SEO metadata for **Bangla and English** posts. No LLM, no network, no API keys.

- **Grapheme-aware length checks** for titles (about 60) and meta descriptions (about 155) that count what a reader sees, not code points. `বাংলা` is 5 code points but 2 characters.
- **Bangla to Latin slugs** with a phonetic mapping (vowels, consonants, kar, ফলা, hasanta, nukta forms, digits) and a small loanword dictionary: `ওয়ার্ডপ্রেস এসইও টিপস` becomes `wordpress-seo-tips`. English passes through.
- **JSON-LD** for `Article` (or `BlogPosting` / `NewsArticle`) and `FAQPage`, from a simple YAML or JSON file. Bangla stays readable in the output.
- **Head meta tags**: `<title>`, meta description, canonical link, Open Graph (including `article:*` and `og:locale`) and Twitter/X card tags from the same post file, shortened on grapheme boundaries so a conjunct is never cut in half.
- **`check` command**: title and description issues, keyword presence (inflection-aware for Bangla), stopword-aware keyword density with top terms, and readability hints.

## Install

Requires Python 3.9+.

```bash
pip install .            # or: pip install -e ".[dev]"
```

## CLI

```bash
bangla-seo length "ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়"
# 27 graphemes (42 code points, 114 bytes) - OK (recommended 20-60)

bangla-seo length "A very long description ..." --kind description

bangla-seo slug "ওয়ার্ডপ্রেস এসইও টিপস ২০২৬"
# wordpress-seo-tips-2026
bangla-seo slug "আমি বাংলায় গান গাই"
# ami-banglay-gan-gai
bangla-seo slug "Hello, Café World" --max-length 20
# hello-cafe-world

bangla-seo schema examples/post-bn.yaml --script-tag      # Article + FAQPage
bangla-seo schema examples/post-en.json --type faq
bangla-seo schema examples/post-en.json --type article --article-type BlogPosting

bangla-seo meta examples/post-bn.yaml --site-name "Example Blog" --twitter-site @example
bangla-seo meta examples/post-bn.yaml --with-schema > head.html   # tags + JSON-LD in one go

bangla-seo check --title "ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়" \
                 --description "দ্রুত" --keyword "ওয়ার্ডপ্রেস" \
                 --body-file examples/body-bn.txt
```

Output of the last command:

```text
Title:       27 graphemes
Description: 2 graphemes
Body:        23 words, 4 sentences, avg 5.8 words/sentence, ~0.1 min read
Keyword density: 4.35% of all words, 6.25% of 16 content words (stopwords removed)
[WARNING] Description is only 2 graphemes; aim for at least 50.
[WARNING] Keyword 'ওয়ার্ডপ্রেস' does not appear in the description.
[INFO   ] The body has 23 words; pages under 300 words rarely rank for competitive queries.
[WARNING] Keyword density is 4.35% (above 3.0%); it may read as stuffing.
```

### Checking many posts at once

`check` also accepts any number of post files (YAML or JSON) or quoted glob patterns. Each file may define `title`, `description`, `keyword` (or `keywords`, the first one is used), and `body` or `body_file` (a path relative to the post). The files are checked, issues are listed per file, and a summary table follows:

```bash
bangla-seo check "content/posts/*.yaml"
bangla-seo check examples/post-bn.yaml examples/post-en.json --json
```

```text
File                   Errors  Warnings  Status
---------------------  ------  --------  ------
examples/post-bn.yaml  0       0         ok
examples/post-en.json  0       0         ok

2 file(s) checked, 0 with errors, 0 warning(s).
```

The command exits `1` if any file has an error or cannot be read, which makes it suitable for CI. `--title`, `--description`, `--keyword` and `--body-file` cannot be combined with file arguments.

Exit codes: `length` and `check` exit `1` when the text is out of range / has errors, `schema` and `meta` exit `2` on bad input.

### Markdown posts with front matter

`check` and `schema` also read Markdown files whose metadata lives in a YAML front matter block (Hugo, Jekyll and Astro style). The text below the block is used as the `body`, unless the front matter sets `body` or `body_file` itself:

```markdown
---
title: ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়
description: ...
keywords: [ওয়ার্ডপ্রেস, গতি]
---

Post content starts here...
```

```bash
bangla-seo check "content/posts/*.md"
```

A `.md` / `.markdown` file without a closing `---` fence is reported as an error rather than silently skipped.

### Schema input

```yaml
title: ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়
description: ...
url: https://example.com/wordpress-speed-up/
image: https://example.com/images/speed.webp
language: bn
author: { name: Saizul Amin, url: https://saizul.com }   # or just a string
publisher: { name: Example Blog, logo: https://example.com/logo.png }
date_published: 2026-01-10
date_modified: 2026-02-01T09:30:00+06:00
keywords: [ওয়ার্ডপ্রেস, গতি, ক্যাশ]
faq:
  - question: ওয়ার্ডপ্রেস সাইট ধীর হয় কেন?
    answer: ভারী থিম, অপ্টিমাইজ না করা ছবি এবং ক্যাশ না থাকা সবচেয়ে সাধারণ কারণ।
```

`title` and `url` are required for Article; `faq` needs at least one question/answer pair for FAQPage. See [`examples/`](examples).

### Head meta tags (Open Graph and Twitter cards)

`meta` reads the same YAML, JSON or Markdown file as `schema` and prints the tags for the page `<head>`:

```bash
bangla-seo meta examples/post-bn.yaml --site-name "Example Blog" \
    --twitter-site @example --title-template "{title} | {site_name}"
```

```html
<title>ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায় | Example Blog</title>
<meta name="description" content="ওয়ার্ডপ্রেস সাইটের গতি বাড়াতে ক্যাশ, ছবি অপ্টিমাইজেশন ও CDN কীভাবে ব্যবহার করবেন, তা ধাপে ধাপে জানুন।">
<link rel="canonical" href="https://example.com/wordpress-speed-up/">
<meta property="og:type" content="article">
<meta property="og:title" content="ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়">
...
<meta property="og:locale" content="bn_BD">
<meta property="og:image" content="https://example.com/images/speed.webp">
<meta property="article:published_time" content="2026-01-10">
<meta property="article:tag" content="ওয়ার্ডপ্রেস">
...
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@example">
```

Besides the schema fields it understands `site_name`, `og_type` (default `article` when the post has an author or dates, otherwise `website`), `locale` (else derived from `language`: `bn` becomes `bn_BD`, `bn-IN` becomes `bn_IN`), `robots`, `image` as either a URL or `{url, alt}`, `image_alt`, and `twitter: {site, creator, card}`. `url` and `image` must be absolute http(s) URLs; handles may be written as `example`, `@example` or a profile URL.

Text is shortened per slot, by graphemes and at a word break where possible: 60 for `<title>`, 155 for the meta description, 95 / 70 for the Open Graph / Twitter titles and 200 for their descriptions. With `--title-template` only the title part is shortened, so the site name suffix stays. Each shortening is reported as a `note:` on stderr; `--no-shorten` turns it off. `--with-schema` appends the Article (and FAQPage, when `faq` is set) JSON-LD, and `--json` prints everything as JSON instead of HTML.

## Library

```python
from bangla_seo_meta import check, check_length, grapheme_len, slugify, build_article, build_faq, build_meta, to_script_tag, truncate

grapheme_len("বাংলাদেশ")             # 4   (len() says 8)
check_length("Short title").status   # "short"
slugify("ব্লগ পোস্টের গাইড")          # "blog-poster-guide"

report = check(
    title="WordPress Speed Guide: 5 Easy Wins",
    description="Caching, images and a CDN explained step by step.",
    keyword="WordPress",
)
report.ok, [i.code for i in report.issues]

truncate("ওয়ার্ডপ্রেস সাইট দ্রুত করার ৫টি সহজ উপায়", 20)   # "ওয়ার্ডপ্রেস সাইট দ্রুত করার…"
print(build_meta({"title": "বাংলা পোস্ট", "language": "bn"}, site_name="Example Blog").to_html())

print(to_script_tag(build_faq({"faq": [{"question": "Why?", "answer": "Because."}]})))
```

## English example

```bash
$ bangla-seo check --title "Speed" --keyword wordpress
Title:       5 graphemes
[WARNING] Title is only 5 graphemes; aim for at least 20.
[WARNING] Keyword 'wordpress' does not appear in the title.
```

## How it works, and its limits

- **Graphemes.** Python's standard library cannot segment grapheme clusters, so `graphemes.py` implements the relevant part of Unicode UAX #29: combining marks (kar, anusvara, visarga, chandrabindu, nukta) and ZWJ/ZWNJ attach to the previous character, and a letter after a hasanta joins the conjunct (`ক্ষ` is one unit). Google actually truncates by **pixel width**, so the limits are guidance; the `check` command adds a hint when a long Bangla title is likely to be cut early because Bangla glyphs are wider than Latin ones. Minimum lengths are lenient since a Bangla grapheme carries more than a Latin letter.
- **Transliteration** is phonetic and deterministic, built for readable URLs, not linguistic accuracy. Schwa deletion is approximated (final consonants drop the inherent "o"), ya-phala doubles the previous consonant (`সত্য` is `sotto`), and some spellings will differ from what you would pick by hand. Extend `translit.LOANWORDS` for brand names and terms you use often.
- **Keyword matching** is case-insensitive, never matches inside a conjunct, and tolerates Bangla case endings (`ওয়ার্ডপ্রেস` is found in `ওয়ার্ডপ্রেসের`). Use `count_term(..., strict=True)` for exact grapheme-boundary matches.
- **Keyword density** is reported two ways: against all words (this drives the stuffing warning) and against content words only, after removing common Bangla and English function words (`এবং`, `জন্য`, `the`, `of` ...) and bare numbers. With a body, `check` also lists the most repeated content words (`Top terms`) so you can see what the text is really about. The stopword list is short and matched exactly (no stemming); extend `bangla_seo_meta.stopwords.STOPWORDS` for your niche. In JSON output these are `content_words`, `keyword_density_content` and `top_terms`.
- **Readability** hints are heuristics (sentence length, paragraph length, thin content, keyword density); sentences end at `. ! ?` or the Bangla danda `।`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT, see [LICENSE](LICENSE). Built by [Saizul Amin](https://saizul.com).

## Run with Docker

A multi-arch image (amd64, arm64) is published to GitHub Container Registry on every change to `main`, so you can run the tool without installing Python:

```bash
docker run --rm -v "$PWD:/work" ghcr.io/saizul/bangla-seo-meta-generator:latest --help
```

Mount the folder that holds your input files (and where reports should be written) at `/work`.
