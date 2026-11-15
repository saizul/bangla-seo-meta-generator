"""Run ``check`` over many post files (YAML / JSON) and summarise the results."""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .checks import ERROR, WARNING, CheckReport, check
from .duplicates import SIMILAR_TITLE_THRESHOLD, DuplicateGroup, Post, find_duplicates, issues_for
from .schema import SchemaError, load_input

_GLOB_CHARS = set("*?[")


@dataclass
class FileResult:
    path: str
    report: Optional[CheckReport] = None
    error: Optional[str] = None  # set when the file could not be read or parsed
    post: Optional[Post] = field(default=None, repr=False)  # fields used by the cross-file checks

    @property
    def errors(self) -> int:
        if self.report is None:
            return 1
        return sum(1 for i in self.report.issues if i.level == ERROR)

    @property
    def warnings(self) -> int:
        return 0 if self.report is None else sum(1 for i in self.report.issues if i.level == WARNING)

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"file": self.path, "ok": self.ok, "errors": self.errors, "warnings": self.warnings}
        if self.error:
            data["error"] = self.error
        if self.report is not None:
            data["report"] = self.report.to_dict()
        return data


def expand_paths(patterns: Sequence[str]) -> List[str]:
    """Expand glob patterns (so quoted globs work on shells that do not expand them).

    Plain paths are kept as given, even if missing, so they are reported as errors.
    Duplicates are dropped; each glob's matches are sorted for stable output.
    """
    seen: Dict[str, None] = {}
    for pattern in patterns:
        if _GLOB_CHARS & set(pattern) and not Path(pattern).exists():
            matches = sorted(glob.glob(pattern, recursive=True))
            if not matches:
                seen.setdefault(pattern, None)  # surfaces as "file not found"
            for match in matches:
                if Path(match).is_file():
                    seen.setdefault(match, None)
        else:
            seen.setdefault(pattern, None)
    return list(seen)


def _keyword(data: Dict[str, Any]) -> Optional[str]:
    keyword = data.get("keyword")
    if keyword:
        return str(keyword)
    keywords = data.get("keywords")
    if isinstance(keywords, list) and keywords:
        return str(keywords[0])
    return None


def check_file(path: str) -> FileResult:
    """Check one post file. ``body`` may be inline or ``body_file`` (relative to the post)."""
    try:
        data = load_input(path)
        body = data.get("body")
        if body is None and data.get("body_file"):
            body = (Path(path).parent / str(data["body_file"])).read_text(encoding="utf-8")
        title, description, keyword = _str(data.get("title")), _str(data.get("description")), _keyword(data)
        report = check(title, description, keyword, _str(body))
        post = Post(path, title, description, _str(data.get("url")), _str(data.get("slug")), keyword)
    except FileNotFoundError:
        return FileResult(path, error="file not found")
    except (SchemaError, OSError, ValueError, UnicodeDecodeError) as exc:
        return FileResult(path, error=str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
    except Exception as exc:  # malformed YAML raises yaml.YAMLError, which is not a ValueError
        return FileResult(path, error=f"invalid file: {type(exc).__name__}")
    return FileResult(path, report=report, post=post)


def _str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def check_files(patterns: Sequence[str], duplicates: bool = True,
                similar_threshold: float = SIMILAR_TITLE_THRESHOLD) -> List[FileResult]:
    """Check every file; with ``duplicates`` also compare the posts with each other.

    Cross-file findings are appended to each affected file's report, so a duplicate
    URL or slug (an error) makes that file fail.
    """
    results = [check_file(p) for p in expand_paths(patterns)]
    if duplicates:
        add_duplicate_issues(results, similar_threshold)
    return results


def add_duplicate_issues(results: Sequence[FileResult],
                         similar_threshold: float = SIMILAR_TITLE_THRESHOLD) -> List[DuplicateGroup]:
    """Run :func:`find_duplicates` over the readable files and attach the issues."""
    groups = find_duplicates([r.post for r in results if r.post is not None], similar_threshold)
    for r in results:
        if r.report is not None:
            r.report.issues.extend(issues_for(r.path, groups))
    return groups


def format_summary(results: Sequence[FileResult]) -> str:
    """Render a plain-text summary table with one row per file and a totals line."""
    rows = [("File", "Errors", "Warnings", "Status")]
    for r in results:
        status = "ERROR: " + r.error if r.error else ("FAIL" if not r.ok else "ok")
        rows.append((r.path, str(r.errors), str(r.warnings), status))
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = []
    for n, row in enumerate(rows):
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(3)) + "  " + row[3])
        if n == 0:
            lines.append("  ".join("-" * widths[i] for i in range(3)) + "  " + "-" * 6)
    failed = sum(1 for r in results if not r.ok)
    lines.append("")
    lines.append(f"{len(results)} file(s) checked, {failed} with errors, "
                 f"{sum(r.warnings for r in results)} warning(s).")
    return "\n".join(lines)
