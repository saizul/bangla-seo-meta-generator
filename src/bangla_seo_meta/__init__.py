"""SEO metadata helpers for Bangla and English posts."""

from .checks import CheckReport, Issue, check
from .graphemes import count_term, grapheme_len, graphemes
from .length import LengthReport, check_length
from .stopwords import STOPWORDS, content_words, is_stopword
from .schema import SchemaError, build_article, build_faq, to_script_tag
from .translit import slugify, transliterate

__version__ = "0.1.0"

__all__ = [
    "STOPWORDS",
    "CheckReport",
    "Issue",
    "LengthReport",
    "SchemaError",
    "build_article",
    "build_faq",
    "check",
    "check_length",
    "content_words",
    "count_term",
    "grapheme_len",
    "graphemes",
    "is_stopword",
    "slugify",
    "to_script_tag",
    "transliterate",
]
