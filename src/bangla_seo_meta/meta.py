"""Build HTML ``<head>`` meta tags: title, description, canonical, Open Graph and Twitter cards.

The input is the same post mapping that ``schema`` reads (YAML, JSON or Markdown
front matter). Titles and descriptions are shortened on grapheme boundaries, so a
Bangla conjunct or vowel sign is never cut in half, and preferably at a word break.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .graphemes import grapheme_len, graphemes
from .length import LIMITS, normalize_space
from .schema import SchemaError, _iso_date, _require

ELLIPSIS = "…"

# Where each text ends up, and how many graphemes it may use there. The <title>
# and meta description follow the search-snippet limits in ``length.LIMITS``;
# social previews show a little more text.
TEXT_LIMITS = {
    "title": LIMITS["title"][1],
    "description": LIMITS["description"][1],
    "og:title": 95,
    "og:description": 200,
    "twitter:title": 70,
    "twitter:description": 200,
    "image_alt": 420,
}

# Default Open Graph locale for a bare language code.
LOCALES = {
    "bn": "bn_BD",
    "en": "en_US",
    "hi": "hi_IN",
    "ur": "ur_PK",
    "ar": "ar_AR",
}

TWITTER_CARDS = ("summary", "summary_large_image")


@dataclass(frozen=True)
class Tag:
    """One element of the document head: ``<title>``, ``<link>`` or ``<meta>``."""

    element: str
    attrs: Tuple[Tuple[str, str], ...] = ()
    text: Optional[str] = None

    def to_html(self) -> str:
        attrs = "".join(f' {key}="{escape(value, quote=True)}"' for key, value in self.attrs)
        if self.element == "title":
            return f"<title>{escape(self.text or '', quote=False)}</title>"
        return f"<{self.element}{attrs}>"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"element": self.element, **dict(self.attrs)}
        if self.text is not None:
            data["text"] = self.text
        return data


@dataclass
class MetaResult:
    tags: List[Tag] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_html(self) -> str:
        return "\n".join(tag.to_html() for tag in self.tags)

    def to_dict(self) -> Dict[str, Any]:
        return {"tags": [tag.to_dict() for tag in self.tags], "notes": list(self.notes)}

    def get(self, key: str) -> Optional[str]:
        """Content of the first tag whose ``name``/``property``/``rel`` is ``key`` (``"title"`` for <title>)."""
        for tag in self.tags:
            if tag.element == "title" and key == "title":
                return tag.text
            attrs = dict(tag.attrs)
            if key in (attrs.get("name"), attrs.get("property")):
                return attrs.get("content")
            if tag.element == "link" and attrs.get("rel") == key:
                return attrs.get("href")
        return None


def truncate(text: str, max_graphemes: int, ellipsis: str = ELLIPSIS) -> str:
    """Shorten ``text`` to at most ``max_graphemes`` user-perceived characters.

    Cuts only on grapheme boundaries and backs up to the last space when one
    falls in the final 30% of the allowed length. Trailing punctuation (including
    the Bangla danda ``।``) is dropped before ``ellipsis`` is appended.
    """
    if max_graphemes < 1:
        raise ValueError("max_graphemes must be at least 1")
    text = normalize_space(text)
    clusters = graphemes(text)
    if len(clusters) <= max_graphemes:
        return text
    room = max_graphemes - len(graphemes(ellipsis))
    if room < 1:
        return "".join(clusters[:max_graphemes])
    head = clusters[:room]
    spaces = [i for i, cluster in enumerate(head) if cluster == " "]
    if spaces and spaces[-1] >= room * 0.7:
        head = head[: spaces[-1]]
    cut = "".join(head).rstrip(" ,;:-–—।.!?")
    return (cut or "".join(clusters[:room])) + ellipsis


def _absolute_url(value: Any, key: str) -> str:
    text = str(value).strip()
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SchemaError(f"{key!r} must be an absolute http(s) URL, got {text!r}")
    return text


def _handle(value: Any, key: str) -> str:
    text = str(value).strip()
    if text.startswith("https://") or text.startswith("http://"):
        text = urlparse(text).path.strip("/")
    text = text.lstrip("@")
    if not text or not all(ch.isalnum() or ch == "_" for ch in text) or len(text) > 15:
        raise SchemaError(f"{key!r} must be a Twitter/X handle such as @example, got {value!r}")
    return "@" + text


def _locale(data: Dict[str, Any]) -> Optional[str]:
    if data.get("locale"):
        return str(data["locale"]).replace("-", "_")
    language = str(data.get("language") or "").strip()
    if not language:
        return None
    if "-" in language or "_" in language:
        lang, region = language.replace("_", "-").split("-", 1)
        return f"{lang.lower()}_{region.upper()}"
    return LOCALES.get(language.lower())


def _image(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(url, alt)``; ``image`` may be a URL or a mapping with url/alt."""
    image = data.get("image")
    if not image:
        return None, None
    if isinstance(image, dict):
        url = _absolute_url(_require(image, "url"), "image.url")
        alt = image.get("alt") or data.get("image_alt")
    else:
        url = _absolute_url(image, "image")
        alt = data.get("image_alt")
    return url, (normalize_space(str(alt)) if alt else None)


_SEPARATORS = " |-–—·:"


def _page_title(
    title: str, template: Optional[str], site_name: Optional[str], shorten: bool, notes: List[str]
) -> str:
    """Render the ``<title>`` text; a long title is shortened so the template's suffix survives."""
    limit = TEXT_LIMITS["title"]
    before = after = ""
    if template:
        try:
            frame = template.format(title="\0", site_name=normalize_space(str(site_name or "")))
        except (KeyError, IndexError, ValueError) as exc:
            raise SchemaError(f"bad title template {template!r}: use {{title}} and {{site_name}}") from exc
        if frame.count("\0") != 1:
            raise SchemaError(f"title template {template!r} must contain {{title}} exactly once")
        before, after = frame.split("\0")
        if not site_name:  # "{title} | {site_name}" without a site name is just the title
            before, after = before.lstrip(_SEPARATORS), after.rstrip(_SEPARATORS)
    budget = limit - grapheme_len(before + after)
    if not shorten or grapheme_len(before + title + after) <= limit:
        return normalize_space(before + title + after)
    if budget < 10:  # the template alone eats the space; shorten the whole thing instead
        full = normalize_space(before + title + after)
        notes.append(f"title shortened from {grapheme_len(full)} to {limit} graphemes")
        return truncate(full, limit)
    notes.append(f"title shortened from {grapheme_len(title)} to {budget} graphemes to fit the template")
    return normalize_space(before + truncate(title, budget) + after)


def build_meta(
    data: Dict[str, Any],
    site_name: Optional[str] = None,
    twitter_site: Optional[str] = None,
    title_template: Optional[str] = None,
    shorten: bool = True,
) -> MetaResult:
    """Create head tags for a post mapping.

    Recognised keys: ``title`` (required), ``description``, ``url`` (canonical),
    ``image`` (URL or ``{url, alt}``), ``image_alt``, ``language`` / ``locale``,
    ``site_name``, ``og_type``, ``robots``, ``author``, ``date_published``,
    ``date_modified``, ``keywords`` and ``twitter`` (``{site, creator, card}``).
    Arguments override the matching keys. ``title_template`` (e.g.
    ``"{title} | {site_name}"``) only affects the ``<title>`` element.
    """
    result = MetaResult()
    tags = result.tags

    def fit(text: str, slot: str) -> str:
        text = normalize_space(text)
        if not shorten:
            return text
        limit = TEXT_LIMITS[slot]
        short = truncate(text, limit)
        if short != text:
            result.notes.append(f"{slot} shortened from {len(graphemes(text))} to {limit} graphemes")
        return short

    def meta(attr: str, key: str, content: str) -> None:
        tags.append(Tag("meta", ((attr, key), ("content", content))))

    title = normalize_space(str(_require(data, "title")))
    description = normalize_space(str(data.get("description") or "")) or None
    url = _absolute_url(data["url"], "url") if data.get("url") else None
    image, image_alt = _image(data)
    site_name = site_name or data.get("site_name")
    twitter = data.get("twitter") or {}
    if not isinstance(twitter, dict):
        raise SchemaError("'twitter' must be a mapping with site, creator and/or card")
    twitter_site = twitter_site or twitter.get("site")
    is_article = bool(data.get("date_published") or data.get("date_modified") or data.get("author"))
    og_type = str(data.get("og_type") or ("article" if is_article else "website"))

    tags.append(Tag("title", text=_page_title(title, title_template, site_name, shorten, result.notes)))
    if description:
        meta("name", "description", fit(description, "description"))
    if data.get("robots"):
        meta("name", "robots", normalize_space(str(data["robots"])))
    if url:
        tags.append(Tag("link", (("rel", "canonical"), ("href", url))))

    meta("property", "og:type", og_type)
    meta("property", "og:title", fit(title, "og:title"))
    if description:
        meta("property", "og:description", fit(description, "og:description"))
    if url:
        meta("property", "og:url", url)
    if site_name:
        meta("property", "og:site_name", normalize_space(str(site_name)))
    locale = _locale(data)
    if locale:
        meta("property", "og:locale", locale)
    if image:
        meta("property", "og:image", image)
        if image.startswith("https://"):
            meta("property", "og:image:secure_url", image)
        if image_alt:
            meta("property", "og:image:alt", fit(image_alt, "image_alt"))

    if og_type == "article":
        if data.get("date_published"):
            meta("property", "article:published_time", _iso_date(data["date_published"], "date_published"))
        if data.get("date_modified"):
            meta("property", "article:modified_time", _iso_date(data["date_modified"], "date_modified"))
        author = data.get("author")
        if isinstance(author, dict):
            author = author.get("url") or author.get("name")
        if author:
            meta("property", "article:author", str(author))
        keywords = data.get("keywords") or []
        if isinstance(keywords, str):
            keywords = keywords.split(",")
        for keyword in keywords:
            keyword = normalize_space(str(keyword))
            if keyword:
                meta("property", "article:tag", keyword)

    card = twitter.get("card") or ("summary_large_image" if image else "summary")
    if card not in TWITTER_CARDS:
        raise SchemaError(f"twitter card must be one of {', '.join(TWITTER_CARDS)}, got {card!r}")
    meta("name", "twitter:card", card)
    meta("name", "twitter:title", fit(title, "twitter:title"))
    if description:
        meta("name", "twitter:description", fit(description, "twitter:description"))
    if image:
        meta("name", "twitter:image", image)
        if image_alt:
            meta("name", "twitter:image:alt", fit(image_alt, "image_alt"))
    if twitter_site:
        meta("name", "twitter:site", _handle(twitter_site, "twitter.site"))
    if twitter.get("creator"):
        meta("name", "twitter:creator", _handle(twitter["creator"], "twitter.creator"))
    return result
