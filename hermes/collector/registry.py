from __future__ import annotations

from collections.abc import Iterable

from hermes.collector.base import OfficialPublicationCollector


class CollectorRegistry:
    def __init__(self) -> None:
        self._collectors: dict[str, OfficialPublicationCollector] = {}

    def register(self, collector: OfficialPublicationCollector) -> None:
        self._collectors[collector.source_code] = collector

    def enabled_collectors(self) -> list[OfficialPublicationCollector]:
        return [collector for collector in self._collectors.values() if collector.enabled]

    def all_collectors(self) -> Iterable[OfficialPublicationCollector]:
        return self._collectors.values()


def build_collector_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    return registry

