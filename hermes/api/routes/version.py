from __future__ import annotations

from fastapi import APIRouter

from hermes.config.settings import get_settings

router = APIRouter(tags=["operational"])


@router.get("/version")
def version() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
    }

