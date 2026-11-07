"""Bangla to Latin transliteration for URL slugs.

The mapping is phonetic and deterministic, tuned for readable URLs rather than
linguistic accuracy. Highlights:

* consonants carry an inherent "o" unless they end the word, carry a vowel sign
  (kar), or are followed by a hasanta (conjunct);
* ya-phala (``্য``) doubles the previous consonant (``সত্য`` -> ``sotto``);
* a small dictionary of common loanwords maps straight to their English
  spelling (``ওয়ার্ডপ্রেস`` -> ``wordpress``);
* non-Bangla text passes through unchanged (accents are folded for slugs).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict

_VIRAMA = "্"
_NUKTA = "়"

_VOWELS = {
    "অ": "o", "আ": "a", "ই": "i", "ঈ": "i", "উ": "u", "ঊ": "u",
    "ঋ": "ri", "এ": "e", "ঐ": "oi", "ও": "o", "ঔ": "ou",
}
_KARS = {
    "া": "a", "ি": "i", "ী": "i", "ু": "u", "ূ": "u",
    "ৃ": "ri", "ে": "e", "ৈ": "oi", "ো": "o", "ৌ": "ou",
}
_CONSONANTS = {
    "ক": "k", "খ": "kh", "গ": "g", "ঘ": "gh", "ঙ": "ng",
    "চ": "ch", "ছ": "chh", "জ": "j", "ঝ": "jh", "ঞ": "n",
    "ট": "t", "ঠ": "th", "ড": "d", "ঢ": "dh", "ণ": "n",
    "ত": "t", "থ": "th", "দ": "d", "ধ": "dh", "ন": "n",
    "প": "p", "ফ": "f", "ব": "b", "ভ": "bh", "ম": "m",
    "য": "j", "র": "r", "ল": "l", "শ": "sh", "ষ": "sh",
    "স": "s", "হ": "h",
}
# Consonants combined with a nukta (NFC splits ড়, ঢ়, য় into base + nukta).
_NUKTA_FORMS = {"ড": "r", "ঢ": "rh", "য": "y"}
_SIGNS = {"ং": "ng", "ঃ": "h", "ঁ": "", "ৎ": "t", "৳": "tk"}
_CONJUNCTS = {"ক্ষ": "kkh", "জ্ঞ": "gg", "ঙ্গ": "ng", "ঙ্ক": "nk", "ঞ্চ": "nch", "ঞ্জ": "nj"}
_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_TRAILING_SIGNS = "ংঃঁ"
_YA = "য"


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


LOANWORDS: Dict[str, str] = {
    _nfc(k): v
    for k, v in {
        "ওয়ার্ডপ্রেস": "wordpress",
        "ওয়েবসাইট": "website",
        "ওয়েব": "web",
        "এসইও": "seo",
        "ডিজাইন": "design",
        "ডেভেলপার": "developer",
        "ডেভেলপমেন্ট": "development",
        "ব্লগ": "blog",
        "গুগল": "google",
        "ফেসবুক": "facebook",
        "ইউটিউব": "youtube",
        "ইন্টারনেট": "internet",
        "কম্পিউটার": "computer",
        "মোবাইল": "mobile",
        "অনলাইন": "online",
        "সফটওয়্যার": "software",
        "টিপস": "tips",
        "গাইড": "guide",
        "বাংলাদেশ": "bangladesh",
        "ঢাকা": "dhaka",
    }.items()
}
_LOAN_KEYS = sorted(LOANWORDS, key=len, reverse=True)
# Bangla suffixes allowed after a loanword (e.g. ওয়ার্ডপ্রেসের = wordpress + er).
_LOAN_SUFFIXES = frozenset(_nfc(s) for s in ("ের", "র", "কে", "এ", "ে", "ও", "গুলো", "গুলি", "টি", "টা"))

_BANGLA_RUN = re.compile("[ঀ-৿‌‍]+")


def _consonant_unit(word: str, i: int):
    """Return (roman, next_index) for the consonant (or listed conjunct) at ``i``."""
    triple = word[i : i + 3]
    if triple in _CONJUNCTS:
        return _CONJUNCTS[triple], i + 3
    roman = _CONSONANTS[word[i]]
    i += 1
    if i < len(word) and word[i] == _NUKTA:
        roman = _NUKTA_FORMS.get(word[i - 1], roman)
        i += 1
    return roman, i


def _has_more_letters(word: str, i: int) -> bool:
    return any(ch not in _TRAILING_SIGNS and ch != "‌" for ch in word[i:])


def phonetic(word: str) -> str:
    """Transliterate one Bangla word with the phonetic rules (no dictionary)."""
    word = _nfc(word).replace("‌", "").replace("‍", "")
    out = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        if ch in _CONSONANTS:
            at_start = not out
            roman, i = _consonant_unit(word, i)
            following = word[i] if i < n else ""
            if following == _VIRAMA:
                i += 1
                if i < n and word[i] == _YA:  # ya-phala
                    i += 1
                    out.append(roman if at_start else roman[0] + roman)
                    if at_start:
                        out.append("y")
                    if i < n and word[i] in _KARS:
                        out.append(_KARS[word[i]])
                        i += 1
                    else:
                        out.append("o")
                else:
                    out.append(roman)  # conjunct: no inherent vowel
            elif following in _KARS:
                out.append(roman + _KARS[following])
                i += 1
            else:
                out.append(roman + ("o" if _has_more_letters(word, i) else ""))
        elif ch in _VOWELS:
            out.append(_VOWELS[ch])
            i += 1
        elif ch in _KARS:
            out.append(_KARS[ch])
            i += 1
        elif ch in _SIGNS:
            out.append(_SIGNS[ch])
            i += 1
        else:
            out.append(ch.translate(_DIGITS))
            i += 1
    return "".join(out)


def transliterate_word(word: str) -> str:
    """Transliterate one Bangla word, preferring the loanword dictionary."""
    word = _nfc(word)
    if word in LOANWORDS:
        return LOANWORDS[word]
    for key in _LOAN_KEYS:
        if word.startswith(key) and word[len(key) :] in _LOAN_SUFFIXES:
            return LOANWORDS[key] + phonetic(word[len(key) :])
    return phonetic(word)


def transliterate(text: str) -> str:
    """Transliterate every Bangla run in ``text``; other characters are untouched."""
    return _BANGLA_RUN.sub(lambda m: transliterate_word(m.group()), text)


def slugify(text: str, max_length: int = 60, separator: str = "-") -> str:
    """Build an ASCII URL slug from Bangla and/or English text.

    The slug is cut at a word boundary when it would exceed ``max_length``.
    """
    ascii_text = unicodedata.normalize("NFKD", transliterate(text)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", separator, ascii_text.lower()).strip(separator)
    if len(slug) > max_length:
        cut = slug[:max_length]
        if slug[max_length] != separator and separator in cut:
            cut = cut.rsplit(separator, 1)[0]
        slug = cut.strip(separator)
    return slug
