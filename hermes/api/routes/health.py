from __future__ import annotations

from fastapi import APIRouter, Response, status

from hermes.config.settings import get_settings
from hermes.database.health import database_health

router = APIRouter(tags=["operational"])


@router.get("/health")
def health(response: Response) -> dict[str, object]:
    settings = get_settings()
    database = database_health()
    service_status = "ok" if database["ok"] else "degraded"

    if not database["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": service_status,
        "service": settings.app_name,
        "environment": settings.environment,
        "database": database,
    }

