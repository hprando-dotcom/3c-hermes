from __future__ import annotations

from datetime import UTC, datetime

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler

from hermes.config.logging import configure_logging
from hermes.config.settings import get_settings
from hermes.scheduler.jobs import run_collection_cycle

logger = structlog.get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    if not settings.enable_scheduler:
        logger.info("scheduler_disabled")
        return

    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        run_collection_cycle,
        trigger="interval",
        seconds=settings.collector_interval_seconds,
        id="official_publication_collection_cycle",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )

    logger.info(
        "scheduler_started",
        interval_seconds=settings.collector_interval_seconds,
        timezone=settings.scheduler_timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    main()

