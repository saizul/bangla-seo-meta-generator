"""Length checks for SEO titles and meta descriptions, measured in graphemes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .graphemes import grapheme_len

# kind -> (recommended minimum, recommended maximum) in graphemes. Bangla graphemes
# are coarser than Latin letters, so the minimums are deliberately lenient.
LIMITS = {
    "title": (20, 60),
    "description": (50, 155),
}


@dataclass(frozen=True)
class LengthReport:
    text: str
    graphemes: int
    codepoints: int
    utf8_bytes: int
    minimum: int
    maximum: int

    @property
    def status(self) -> str:
        """One of ``empty``, ``short``, ``ok`` or ``long``."""
        if self.graphemes == 0:
            return "empty"
        if self.graphemes > self.maximum:
            return "long"
        if self.graphemes < self.minimum:
            return "short"
        return "ok"

    @property
    def remaining(self) -> int:
        """Graphemes left before the maximum (negative when over)."""
        return self.maximum - self.graphemes


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def check_length(
    text: str,
    kind: str = "title",
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> LengthReport:
    """Measure ``text`` against the limits for ``kind`` ("title" or "description")."""
    if kind not in LIMITS:
        raise ValueError(f"kind must be one of {sorted(LIMITS)}, got {kind!r}")
    default_min, default_max = LIMITS[kind]
    cleaned = normalize_space(text)
    return LengthReport(
        text=cleaned,
        graphemes=grapheme_len(cleaned),
        codepoints=len(cleaned),
        utf8_bytes=len(cleaned.encode("utf-8")),
        minimum=default_min if minimum is None else minimum,
        maximum=default_max if maximum is None else maximum,
    )
