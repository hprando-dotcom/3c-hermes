from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True)
class ClassificationResult:
    provider: str
    labels: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    confidence: Decimal | None = None
    model: str | None = None


class PublicationClassifier(ABC):
    provider: str

    @abstractmethod
    def classify(self, text: str, metadata: dict[str, object] | None = None) -> ClassificationResult:
        raise NotImplementedError

