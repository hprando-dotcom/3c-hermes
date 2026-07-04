from __future__ import annotations

from fastapi import FastAPI

from hermes.api.routes.health import router as health_router
from hermes.api.routes.pmsp_ui import router as pmsp_ui_router
from hermes.api.routes.status import router as status_router
from hermes.api.routes.tcesp_ui import router as tcesp_ui_router
from hermes.api.routes.version import router as version_router
from hermes.config.settings import Settings, get_settings
from hermes.config.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.include_router(pmsp_ui_router)
    app.include_router(tcesp_ui_router)
    app.include_router(status_router)
    app.include_router(health_router)
    app.include_router(version_router)
    return app
