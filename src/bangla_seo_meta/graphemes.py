"""Grapheme-cluster segmentation that understands Bangla (and other Indic) scripts.

Python's ``len()`` counts code points, so the Bangla word ``বাংলা`` is "5
characters" although a reader sees two units. The standard library has no
grapheme support and the ``\\X`` regex class needs the third-party ``regex``
module, so this module implements the part of UAX #29 that matters for SEO text:

* combining marks (vowel signs / kar, anusvara, visarga, chandrabindu, nukta)
  attach to the preceding character;
* ZWJ / ZWNJ and variation selectors extend a cluster;
* after a virama (hasanta ``্``) the next letter joins the cluster, so a
  conjunct such as ``ক্ষ`` is one unit;
* CRLF, emoji ZWJ sequences, skin-tone modifiers and flag pairs.
"""

from __future__ import annotations

import unicodedata
from typing import List, Set

ZWNJ = "‌"
ZWJ = "‍"
_VIRAMA_CLASS = 9  # canonical combining class of virama/halant signs


def _ends_with_virama(cluster: str) -> bool:
    stripped = cluster.rstrip(ZWNJ + ZWJ)
    return bool(stripped) and unicodedata.combining(stripped[-1]) == _VIRAMA_CLASS


def _is_regional_indicator(ch: str) -> bool:
    return "\U0001F1E6" <= ch <= "\U0001F1FF"


def _joins(cluster: str, ch: str) -> bool:
    prev = cluster[-1]
    if prev == "\r" and ch == "\n":
        return True
    if prev in "\r\n" or ch in "\r\n":
        return False

    category = unicodedata.category(ch)
    if category in ("Mn", "Mc", "Me") or ch in (ZWJ, ZWNJ):
        return True
    if "\U0001F3FB" <= ch <= "\U0001F3FF":  # emoji skin-tone modifiers
        return True
    if category.startswith("L") and _ends_with_virama(cluster):
        return True  # conjunct: consonant + hasanta + consonant
    if prev == ZWJ and category == "So":
        return True  # emoji ZWJ sequence
    if _is_regional_indicator(ch) and _is_regional_indicator(cluster[-1]) and len(cluster) == 1:
        return True
    return False


def graphemes(text: str) -> List[str]:
    """Split ``text`` into user-perceived characters (grapheme clusters)."""
    clusters: List[str] = []
    for ch in unicodedata.normalize("NFC", text):
        if clusters and _joins(clusters[-1], ch):
            clusters[-1] += ch
        else:
            clusters.append(ch)
    return clusters


def grapheme_len(text: str) -> int:
    """Number of user-perceived characters in ``text``."""
    return len(graphemes(text))


def boundaries(text: str) -> Set[int]:
    """Code-point offsets (in the NFC form of ``text``) where a cluster starts or ends."""
    offsets = {0}
    position = 0
    for cluster in graphemes(text):
        position += len(cluster)
        offsets.add(position)
    return offsets


def count_term(text: str, term: str, strict: bool = False) -> int:
    """Count case-insensitive occurrences of ``term`` in ``text``.

    A match must start on a grapheme boundary and must not end inside a
    conjunct (before a hasanta). By default it may end just before a vowel
    sign, so the keyword ``ওয়ার্ডপ্রেস`` is found in the inflected form
    ``ওয়ার্ডপ্রেসের``, which is how Bangla attaches case endings.

    With ``strict=True`` the match must also end on a grapheme boundary, so
    ``কথ`` is *not* found inside ``কথা``.
    """
    haystack = unicodedata.normalize("NFC", text).casefold()
    needle = unicodedata.normalize("NFC", term).casefold().strip()
    if not needle:
        return 0
    allowed = boundaries(haystack)  # computed on the folded string so offsets agree
    count = start = 0
    while True:
        index = haystack.find(needle, start)
        if index == -1:
            return count
        end = index + len(needle)
        if index in allowed and (end in allowed or (not strict and _may_inflect(haystack, end))):
            count += 1
        start = index + 1


def _may_inflect(text: str, end: int) -> bool:
    """True when ``text[end]`` is a combining mark other than a virama."""
    following = text[end]
    return unicodedata.category(following) in ("Mn", "Mc") and unicodedata.combining(following) != _VIRAMA_CLASS
