"""Build schema.org JSON-LD (Article, FAQPage) from simple dict / YAML / JSON input."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

CONTEXT = "https://schema.org"


class SchemaError(ValueError):
    """Raised when the input is missing a field the requested schema needs."""


def load_input(path: Union[str, Path]) -> Dict[str, Any]:
    """Read a ``.json`` file, or YAML for any other extension."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SchemaError(f"{path} must contain a mapping at the top level")
    return data


def _require(data: Dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value in (None, "", [], {}):
        raise SchemaError(f"missing required field: {key!r}")
    return value


def _iso_date(value: Any, key: str) -> str:
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise SchemaError(f"{key!r} must be an ISO 8601 date, got {text!r}") from None
    return text


def _entity(value: Any, default_type: str) -> Dict[str, Any]:
    """Accept either a plain name or a mapping with name/url/type."""
    if isinstance(value, str):
        return {"@type": default_type, "name": value}
    entity = {"@type": value.get("type", default_type), "name": _require(value, "name")}
    if value.get("url"):
        entity["url"] = value["url"]
    return entity


def build_article(data: Dict[str, Any], article_type: str = "Article") -> Dict[str, Any]:
    """Create an Article (or BlogPosting / NewsArticle) JSON-LD object."""
    url = _require(data, "url")
    schema: Dict[str, Any] = {
        "@context": CONTEXT,
        "@type": article_type,
        "headline": _require(data, "title"),
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    if data.get("description"):
        schema["description"] = data["description"]
    if data.get("image"):
        schema["image"] = data["image"]
    if data.get("author"):
        schema["author"] = _entity(data["author"], "Person")
    if data.get("publisher"):
        publisher = _entity(data["publisher"], "Organization")
        logo = data["publisher"].get("logo") if isinstance(data["publisher"], dict) else None
        if logo:
            publisher["logo"] = {"@type": "ImageObject", "url": logo}
        schema["publisher"] = publisher
    if data.get("date_published"):
        schema["datePublished"] = _iso_date(data["date_published"], "date_published")
    if data.get("date_modified"):
        schema["dateModified"] = _iso_date(data["date_modified"], "date_modified")
    if data.get("language"):
        schema["inLanguage"] = data["language"]
    keywords = data.get("keywords")
    if keywords:
        schema["keywords"] = ", ".join(keywords) if isinstance(keywords, list) else keywords
    return schema


def build_faq(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a FAQPage JSON-LD object from ``data["faq"]`` (question/answer pairs)."""
    items = _require(data, "faq")
    if not isinstance(items, list):
        raise SchemaError("'faq' must be a list of {question, answer} items")
    entities: List[Dict[str, Any]] = []
    for position, item in enumerate(items, start=1):
        question = str(item.get("question", "")).strip() if isinstance(item, dict) else ""
        answer = str(item.get("answer", "")).strip() if isinstance(item, dict) else ""
        if not question or not answer:
            raise SchemaError(f"faq item {position} needs both 'question' and 'answer'")
        entities.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    return {"@context": CONTEXT, "@type": "FAQPage", "mainEntity": entities}


def to_json(schema: Dict[str, Any], indent: int = 2) -> str:
    """Serialise without escaping Bangla (``ensure_ascii=False``)."""
    return json.dumps(schema, ensure_ascii=False, indent=indent)


def to_script_tag(schema: Dict[str, Any]) -> str:
    """Wrap a schema in a ``<script type="application/ld+json">`` element."""
    body = to_json(schema).replace("</", "<\\/")  # keep the payload from closing the tag
    return f'<script type="application/ld+json">\n{body}\n</script>'
