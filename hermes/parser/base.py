from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from hermes.collector.base import CollectionItem


@dataclass(slots=True)
class ParsedPublication:
    source_code: str
    source_name: str
    external_id: str | None = None
    api_name: str | None = None
    organization: str | None = None
    entity: str | None = None
    state: str | None = None
    municipality: str | None = None
    publication_type: str | None = None
    object_description: str | None = None
    modality: str | None = None
    situation: str | None = None
    number: str | None = None
    year: int | None = None
    winner_company_name: str | None = None
    winner_cnpj: str | None = None
    estimated_value: Decimal | None = None
    awarded_value: Decimal | None = None
    contracted_value: Decimal | None = None
    addendum_value: Decimal | None = None
    deadline: str | None = None
    validity_start: date | None = None
    validity_end: date | None = None
    published_at: datetime | None = None
    event_date: date | None = None
    links: list[dict[str, object]] = field(default_factory=list)
    raw_payload: dict[str, object] = field(default_factory=dict)
    normalized_payload: dict[str, object] = field(default_factory=dict)
    raw_text: str | None = None
    clean_text: str | None = None


class PublicationParser(ABC):
    @abstractmethod
    def parse(self, item: CollectionItem) -> ParsedPublication:
        raise NotImplementedError

