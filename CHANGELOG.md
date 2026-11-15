# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- Cross-file duplicate checks when `check` is given several post files: identical canonical URLs and slugs (errors), identical titles and meta descriptions after Unicode/case/punctuation normalisation (warnings), near-duplicate titles by content-word Jaccard similarity and shared primary keywords (info). Findings are attached to every file involved, summarised after the table, and returned under `duplicates` in `--json` output.
- `--no-duplicates` to skip the cross-file checks and `--similar-titles RATIO` to tune (or, above 1, disable) the near-duplicate title check.
- `find_duplicates()`, `Post` and `DuplicateGroup` in the library API.
- `meta` command and `build_meta()` that generate the page `<head>` tags from a post file: `<title>`, meta description, canonical link, Open Graph (`og:*`, `article:*`, `og:locale` derived from `language`) and Twitter/X card tags.
- Grapheme-safe `truncate()` that shortens titles and descriptions per slot (search snippet, Open Graph, Twitter) at word breaks without splitting Bangla conjuncts or vowel signs; shortenings are reported as notes.
- `--title-template` (e.g. `"{title} | {site_name}"`) that keeps the site name when a long title is shortened, `--with-schema` to emit the JSON-LD alongside the tags, and `--json` output.

### Changed

- Batch `check` now exits `1` when two posts share a canonical URL or slug; pass `--no-duplicates` for the previous behaviour.
- `requires-python` is now `>=3.10`, matching the CI matrix and the README badge.

## 0.1.0 and earlier

- See the git history for changes before this file was added.
