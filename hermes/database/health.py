from __future__ import annotations

from time import perf_counter

from sqlalchemy import text

from hermes.database.session import SessionLocal


def database_health() -> dict[str, object]:
    started = perf_counter()
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": True, "latency_ms": elapsed_ms}
    except Exception as exc:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": False, "latency_ms": elapsed_ms, "error": exc.__class__.__name__}

