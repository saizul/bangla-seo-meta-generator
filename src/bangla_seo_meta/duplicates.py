"""Cross-file checks for a batch of posts: duplicate titles, descriptions, URLs and slugs.

A single post can look fine on its own and still hurt the site when another post
uses the same ``<title>``, the same meta description or the same canonical URL.
:func:`find_duplicates` compares the posts of a batch with each other:

* **url** - two posts claim the same canonical URL (error).
* **slug** - two posts would be published under the same slug (error). The slug is
  the ``slug`` field, else the last path segment of ``url``, else the slug of the title.
* **title** / **description** - identical text after Unicode (NFC) normalisation,
  case folding, whitespace collapsing and trimming of trailing punctuation,
  including the Bangla danda (warning).
* **similar-title** - titles that share most of their content words, measured with
  Jaccard similarity after removing stopwords (info).
* **keyword** - several posts target the same primary keyword and may compete
  with each other in search results (info).
"""

from __future__ import annotations

import string
import unicodedata
from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from .checks import ERROR, INFO, WARNING, Issue, split_words
from .stopwords import content_words
from .translit import slugify

SIMILAR_TITLE_THRESHOLD = 0.8
_TRAILING = string.punctuation + "।॥“”‘’–—… \t"

# kind -> (issue level, human label)
KINDS: Dict[str, Tuple[str, str]] = {
    "url": (ERROR, "canonical URL"),
    "slug": (ERROR, "slug"),
    "title": (WARNING, "title"),
    "description": (WARNING, "description"),
    "similar-title": (INFO, "a very similar title"),
    "keyword": (INFO, "primary keyword"),
}


@dataclass
class Post:
    """The fields of one post that take part in the cross-file comparison."""

    path: str
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    slug: Optional[str] = None
    keyword: Optional[str] = None


@dataclass
class DuplicateGroup:
    kind: str
    value: str
    files: List[str] = field(default_factory=list)
    similarity: Optional[float] = None  # only for ``similar-title``

    @property
    def level(self) -> str:
        return KINDS[self.kind][0]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level
        if self.similarity is None:
            data.pop("similarity")
        return data


def normalise_text(text: str) -> str:
    """NFC, case-folded, single-spaced text without trailing punctuation."""
    text = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    return text.rstrip(_TRAILING).strip()


def normalise_url(url: str) -> str:
    """Compare URLs the way a crawler would: case-insensitive host, no fragment, no trailing slash."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.port and not (
        (parts.scheme == "http" and parts.port == 80) or (parts.scheme == "https" and parts.port == 443)
    ):
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def post_slug(post: Post) -> Optional[str]:
    """The slug a post will be published under, or ``None`` when it cannot be derived."""
    if post.slug and post.slug.strip():
        return slugify(post.slug)
    if post.url:
        segments = [s for s in urlsplit(post.url.strip()).path.split("/") if s]
        if segments:
            return segments[-1].lower()
        return None  # the site root has no slug
    if post.title and post.title.strip():
        return slugify(post.title) or None
    return None


def title_terms(title: str) -> frozenset:
    return frozenset(normalise_text(w) for w in content_words(split_words(title)) if normalise_text(w))


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _group(
    posts: Iterable[Post],
    kind: str,
    key: Callable[[Post], Optional[str]],
    display: Optional[Callable[[Post], Optional[str]]] = None,
) -> List[DuplicateGroup]:
    """Bucket posts by ``key``; the group shows ``display`` of its first post (else the key)."""
    buckets: Dict[str, List[str]] = {}
    shown: Dict[str, str] = {}
    for post in posts:
        value = key(post)
        if not value:
            continue
        if post.path in buckets.get(value, []):
            continue
        buckets.setdefault(value, []).append(post.path)
        raw = display(post) if display else None
        shown.setdefault(value, " ".join(raw.split()) if raw else value)
    return [DuplicateGroup(kind, shown[v], files) for v, files in buckets.items() if len(files) > 1]


def _similar_titles(posts: Sequence[Post], threshold: float, exact: List[DuplicateGroup]) -> List[DuplicateGroup]:
    exact_pairs = {frozenset(pair) for g in exact for pair in combinations(g.files, 2)}
    terms = [(p, title_terms(p.title)) for p in posts if p.title and p.title.strip()]
    groups = []
    for (a, ta), (b, tb) in combinations(terms, 2):
        if frozenset((a.path, b.path)) in exact_pairs or len(ta) < 2 or len(tb) < 2:
            continue
        score = jaccard(ta, tb)
        if score >= threshold:
            groups.append(DuplicateGroup("similar-title", a.title.strip(), [a.path, b.path], round(score, 2)))
    return groups


def find_duplicates(posts: Sequence[Post], similar_threshold: float = SIMILAR_TITLE_THRESHOLD) -> List[DuplicateGroup]:
    """Compare every post with the others and return one group per shared value.

    Set ``similar_threshold`` above 1 to turn off the near-duplicate title check.
    """
    titles = _group(posts, "title", lambda p: normalise_text(p.title) if p.title else None, lambda p: p.title)
    groups = _group(posts, "url", lambda p: normalise_url(p.url) if p.url and p.url.strip() else None)
    groups += _group(posts, "slug", post_slug)
    groups += titles
    groups += _group(
        posts, "description", lambda p: normalise_text(p.description) if p.description else None, lambda p: p.description
    )
    if similar_threshold <= 1:
        groups += _similar_titles(posts, similar_threshold, titles)
    groups += _group(posts, "keyword", lambda p: normalise_text(p.keyword) if p.keyword else None, lambda p: p.keyword)
    return groups


def issues_for(path: str, groups: Iterable[DuplicateGroup]) -> List[Issue]:
    """The issues that ``path`` should report for the groups it belongs to."""
    issues = []
    for group in groups:
        if path not in group.files:
            continue
        others = ", ".join(f for f in group.files if f != path)
        label = KINDS[group.kind][1]
        if group.kind == "similar-title":
            message = f"Title is {int(group.similarity * 100)}% similar to the title of {others}."
        elif group.kind == "keyword":
            message = f"Primary keyword {group.value!r} is also targeted by {others}; the posts may compete in search."
        else:
            message = f"Same {label} as {others}: {group.value!r}."
        issues.append(Issue(group.level, f"duplicate-{group.kind}", message))
    return issues
