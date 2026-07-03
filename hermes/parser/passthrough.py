from __future__ import annotations

import re

from hermes.collector.base import CollectionItem
from hermes.parser.base import ParsedPublication, PublicationParser


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip()


class PassthroughParser(PublicationParser):
    def parse(self, item: CollectionItem) -> ParsedPublication:
        link = {"url": item.url, "kind": "source"} if item.url else None
        return ParsedPublication(
            source_code=item.source_code,
            source_name=item.source_name,
            external_id=item.external_id,
            api_name=item.api_name,
            published_at=item.published_at,
            links=[link] if link else [],
            raw_payload=item.raw_payload,
            normalized_payload={},
            raw_text=item.raw_text,
            clean_text=clean_text(item.raw_text),
        )

