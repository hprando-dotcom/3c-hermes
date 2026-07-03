from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from hermes.classifier.keyword import KeywordEngineeringClassifier
from hermes.collector.base import CollectorContext, OfficialPublicationCollector
from hermes.collector.registry import build_collector_registry
from hermes.config.settings import get_settings
from hermes.database.models import CollectionRun, Source
from hermes.database.session import SessionLocal
from hermes.parser.passthrough import PassthroughParser
from hermes.services.ingestion import IngestionService

logger = structlog.get_logger(__name__)


def run_collection_cycle() -> None:
    settings = get_settings()
    started_at = datetime.now(UTC)
    since = started_at - timedelta(days=settings.collector_initial_lookback_days)
    context = CollectorContext(started_at=started_at, since=since, until=started_at)
    registry = build_collector_registry()
    collectors = registry.enabled_collectors()

    if not collectors:
        logger.info("collector_cycle_no_collectors_registered")
        return

    with SessionLocal() as session:
        for collector in collectors:
            _run_collector(session, collector, context)


def _run_collector(session: Session, collector: OfficialPublicationCollector, context: CollectorContext) -> None:
    source = _get_or_create_source(session, collector)
    run = CollectionRun(source_id=source.id, status="running", metadata_json={"source_code": collector.source_code})
    session.add(run)
    session.commit()

    service = IngestionService(
        session=session,
        parser=PassthroughParser(),
        classifier=KeywordEngineeringClassifier(),
    )

    try:
        records_found = 0
        inserted = 0
        updated = 0
        for item in collector.collect(context):
            records_found += 1
            result = service.ingest(item)
            inserted += int(result == "inserted")
            updated += int(result == "updated")

        run.status = "success"
        run.records_found = records_found
        run.records_inserted = inserted
        run.records_updated = updated
        run.finished_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "collector_cycle_finished",
            source_code=collector.source_code,
            records_found=records_found,
            inserted=inserted,
            updated=updated,
        )
    except Exception as exc:
        session.rollback()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()
        logger.exception("collector_cycle_failed", source_code=collector.source_code)


def _get_or_create_source(session: Session, collector: OfficialPublicationCollector) -> Source:
    source = session.query(Source).filter(Source.code == collector.source_code).one_or_none()
    if source is not None:
        return source

    source = Source(
        code=collector.source_code,
        name=collector.source_name,
        enabled=True,
        metadata_json={"registered_by": "collector_registry"},
    )
    session.add(source)
    session.commit()
    return source

