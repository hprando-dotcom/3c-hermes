from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CollectorContext:
    started_at: datetime
    since: datetime | None = None
    until: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class CollectionItem:
    source_code: str
    source_name: str
    external_id: str | None = None
    api_name: str | None = None
    url: str | None = None
    raw_payload: dict[str, object] = field(default_factory=dict)
    raw_text: str | None = None
    collected_at: datetime | None = None
    published_at: datetime | None = None


class OfficialPublicationCollector(ABC):
    source_code: str
    source_name: str
    enabled: bool = True

    @abstractmethod
    def collect(self, context: CollectorContext) -> Iterable[CollectionItem]:
        raise NotImplementedError

