from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

PUBLICATION_KEYWORDS = (
    "diario",
    "diário",
    "publicacao",
    "publicação",
    "edital",
    "licitacao",
    "licitação",
    "contrato",
    "extrato",
    "decreto",
    "portaria",
    "ata",
    "pdf",
)


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, Any]] = []
        self.title_parts: list[str] = []
        self._current_link: dict[str, Any] | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a" and attrs_dict.get("href"):
            self._current_link = {
                "href": attrs_dict["href"].strip(),
                "text": "",
                "title": attrs_dict.get("title") or "",
                "rel": attrs_dict.get("rel") or "",
            }

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._current_link is not None:
            self._current_link["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "a" and self._current_link is not None:
            self._current_link["text"] = clean_text(self._current_link["text"] or self._current_link["title"])
            self.links.append(self._current_link)
            self._current_link = None


def extract_title(html: str) -> str | None:
    parser = LinkExtractor()
    parser.feed(html or "")
    title = clean_text(" ".join(parser.title_parts))
    return title or None


def extract_links(html: str, base_url: str) -> list[dict[str, Any]]:
    parser = LinkExtractor()
    parser.feed(html or "")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in parser.links:
        absolute_url = urljoin(base_url, raw["href"])
        if not absolute_url.lower().startswith(("http://", "https://")):
            continue
        normalized_key = absolute_url.split("#", 1)[0]
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        link = {
            "url": absolute_url,
            "text": clean_text(raw.get("text")),
            "is_pdf": is_pdf_url(absolute_url),
            "is_same_domain": same_domain(base_url, absolute_url),
        }
        link["looks_like_publication"] = looks_like_publication(link)
        links.append(link)
    return links


def extract_publication_candidates(html: str, base_url: str, *, limit: int = 100) -> list[dict[str, Any]]:
    candidates = [link for link in extract_links(html, base_url) if link["looks_like_publication"] or link["is_pdf"]]
    return [
        {
            "source_url": base_url,
            "url": item["url"],
            "title": item["text"] or item["url"].rsplit("/", 1)[-1],
            "text": item["text"],
            "publication_type": "pdf" if item["is_pdf"] else "html",
            "raw": item,
        }
        for item in candidates[:limit]
    ]


def extract_visible_text(html: str, *, limit: int = 5000) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)[:limit]


def looks_like_publication(link: dict[str, Any]) -> bool:
    haystack = f"{link.get('url', '')} {link.get('text', '')}".lower()
    return any(keyword in haystack for keyword in PUBLICATION_KEYWORDS)


def is_pdf_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith(".pdf") or ".pdf/" in path


def same_domain(base_url: str, url: str) -> bool:
    return urlsplit(base_url).netloc.lower() == urlsplit(url).netloc.lower()


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())
