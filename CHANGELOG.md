# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- `meta` command and `build_meta()` that generate the page `<head>` tags from a post file: `<title>`, meta description, canonical link, Open Graph (`og:*`, `article:*`, `og:locale` derived from `language`) and Twitter/X card tags.
- Grapheme-safe `truncate()` that shortens titles and descriptions per slot (search snippet, Open Graph, Twitter) at word breaks without splitting Bangla conjuncts or vowel signs; shortenings are reported as notes.
- `--title-template` (e.g. `"{title} | {site_name}"`) that keeps the site name when a long title is shortened, `--with-schema` to emit the JSON-LD alongside the tags, and `--json` output.

## 0.1.0 and earlier

- See the git history for changes before this file was added.
