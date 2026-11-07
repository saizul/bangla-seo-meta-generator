"""The ``check`` command: title/description issues, keyword presence, readability hints."""

from __future__ import annotations

import re
import string
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .graphemes import count_term
from .length import check_length

ERROR, WARNING, INFO = "error", "warning", "info"

_BANGLA = re.compile("[ঀ-৿]")
_SENTENCE_END = re.compile(r"[.!?।]+(?:\s+|$)")  # includes the Bangla danda
_STRIP = string.punctuation + "।॥“”‘’–—…"
_BANGLA_TITLE_SOFT_MAX = 50
MAX_SENTENCE_WORDS = 20
MAX_PARAGRAPH_WORDS = 120
THIN_CONTENT_WORDS = 300
MAX_KEYWORD_DENSITY = 3.0  # percent
WORDS_PER_MINUTE = 200


@dataclass
class Issue:
    level: str
    code: str
    message: str


@dataclass
class Readability:
    words: int = 0
    sentences: int = 0
    avg_sentence_words: float = 0.0
    longest_sentence_words: int = 0
    reading_minutes: float = 0.0
    keyword_density: Optional[float] = None


@dataclass
class CheckReport:
    issues: List[Issue] = field(default_factory=list)
    title_graphemes: Optional[int] = None
    description_graphemes: Optional[int] = None
    readability: Optional[Readability] = None

    @property
    def ok(self) -> bool:
        return not any(issue.level == ERROR for issue in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "ok": self.ok}


def split_words(text: str) -> List[str]:
    """Whitespace tokenisation with punctuation trimmed.

    ``re``'s ``\\w`` does not match Bangla vowel signs (they are combining
    marks), so splitting on word characters would cut Bangla words apart.
    """
    return [token for token in (t.strip(_STRIP) for t in text.split()) if token]


def analyze_readability(text: str, keyword: Optional[str] = None) -> Readability:
    words = split_words(text)
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    lengths = [len(split_words(s)) for s in sentences]
    stats = Readability(
        words=len(words),
        sentences=len(sentences),
        avg_sentence_words=round(sum(lengths) / len(lengths), 1) if lengths else 0.0,
        longest_sentence_words=max(lengths, default=0),
        reading_minutes=round(len(words) / WORDS_PER_MINUTE, 1),
    )
    if keyword and words:
        stats.keyword_density = round(count_term(text, keyword) * len(split_words(keyword)) * 100 / len(words), 2)
    return stats


def _check_field(report: CheckReport, kind: str, text: Optional[str]) -> None:
    if text is None:
        return
    length = check_length(text, kind)
    setattr(report, f"{kind}_graphemes", length.graphemes)
    label = kind.capitalize()
    if length.status == "empty":
        report.issues.append(Issue(ERROR, f"{kind}-empty", f"{label} is empty."))
    elif length.status == "long":
        report.issues.append(Issue(WARNING, f"{kind}-long", f"{label} is {length.graphemes} graphemes; it will likely be truncated above {length.maximum}."))
    elif length.status == "short":
        report.issues.append(Issue(WARNING, f"{kind}-short", f"{label} is only {length.graphemes} graphemes; aim for at least {length.minimum}."))
    if kind == "title" and _BANGLA.search(length.text) and _BANGLA_TITLE_SOFT_MAX < length.graphemes <= length.maximum:
        report.issues.append(Issue(INFO, "title-bangla-width", f"Bangla glyphs are wider than Latin ones and Google truncates by pixel width; keep Bangla titles near {_BANGLA_TITLE_SOFT_MAX} graphemes."))


def check(
    title: Optional[str] = None,
    description: Optional[str] = None,
    keyword: Optional[str] = None,
    body: Optional[str] = None,
) -> CheckReport:
    """Analyse SEO metadata (and optionally the article body) and report issues."""
    report = CheckReport()
    _check_field(report, "title", title)
    _check_field(report, "description", description)

    if title and description and " ".join(title.split()).casefold() == " ".join(description.split()).casefold():
        report.issues.append(Issue(WARNING, "title-equals-description", "Title and description are identical; use the description to add detail."))

    if keyword:
        if title is not None and not count_term(title, keyword):
            report.issues.append(Issue(WARNING, "keyword-missing-title", f"Keyword {keyword!r} does not appear in the title."))
        if description is not None and not count_term(description, keyword):
            report.issues.append(Issue(WARNING, "keyword-missing-description", f"Keyword {keyword!r} does not appear in the description."))
        if body is not None:
            intro = " ".join(body.split()[:100])
            if not count_term(intro, keyword):
                report.issues.append(Issue(INFO, "keyword-missing-intro", f"Keyword {keyword!r} is not in the first 100 words of the body."))

    if body is not None:
        stats = analyze_readability(body, keyword)
        report.readability = stats
        if stats.avg_sentence_words > MAX_SENTENCE_WORDS:
            report.issues.append(Issue(INFO, "long-sentences", f"Sentences average {stats.avg_sentence_words} words; aim for {MAX_SENTENCE_WORDS} or fewer."))
        if any(len(split_words(p)) > MAX_PARAGRAPH_WORDS for p in re.split(r"\n\s*\n", body)):
            report.issues.append(Issue(INFO, "long-paragraph", f"A paragraph exceeds {MAX_PARAGRAPH_WORDS} words; break it up."))
        if stats.words < THIN_CONTENT_WORDS:
            report.issues.append(Issue(INFO, "thin-content", f"The body has {stats.words} words; pages under {THIN_CONTENT_WORDS} words rarely rank for competitive queries."))
        if stats.keyword_density is not None and stats.keyword_density > MAX_KEYWORD_DENSITY:
            report.issues.append(Issue(WARNING, "keyword-stuffing", f"Keyword density is {stats.keyword_density}% (above {MAX_KEYWORD_DENSITY}%); it may read as stuffing."))

    return report
