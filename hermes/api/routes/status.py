from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, safe
from hermes.config.settings import get_settings
from hermes.database.models import PmspLicitacao, TceSpDespesa, TceSpMunicipio, TceSpReceita
from hermes.database.session import get_session

router = APIRouter(tags=["operational"])


@router.get("/status", response_class=HTMLResponse, include_in_schema=False)
def status_page(session: Session = Depends(get_session)) -> HTMLResponse:
    settings = get_settings()
    db_ok = database_is_connected(session)
    counts = {
        "pmsp_licitacoes": safe_count(session, PmspLicitacao),
        "tcesp_municipios": safe_count(session, TceSpMunicipio),
        "tcesp_despesas": safe_count(session, TceSpDespesa),
        "tcesp_receitas": safe_count(session, TceSpReceita),
    }
    alerts = build_alerts(db_ok, counts)
    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Status HERMES</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <div class="metrics">
        <div><span>API</span><strong>online</strong></div>
        <div><span>Banco</span><strong>{'conectado' if db_ok else 'indisponível'}</strong></div>
        <div><span>Versão</span><strong>{safe(settings.version)}</strong></div>
      </div>
      <div class="grid">
        {render_count_panel("PMSP Licitações", counts["pmsp_licitacoes"])}
        {render_count_panel("TCE-SP Municípios", counts["tcesp_municipios"])}
        {render_count_panel("TCE-SP Despesas", counts["tcesp_despesas"])}
        {render_count_panel("TCE-SP Receitas", counts["tcesp_receitas"])}
      </div>
      {render_alerts(alerts)}
      <p class="muted">Ambiente: {safe(settings.environment)} | Commit: {safe(current_commit())} | Leitura: {safe(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>
    </section>
    """
    return html_page("Status HERMES", body)


def database_is_connected(session: Session) -> bool:
    try:
        session.scalar(select(1))
        return True
    except SQLAlchemyError:
        return False


def safe_count(session: Session, model: Any) -> int | str:
    try:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)
    except SQLAlchemyError as exc:
        return f"erro: {exc.__class__.__name__}"


def render_count_panel(title: str, count: int | str) -> str:
    return f"""
    <section class="mini-panel">
      <h2>{safe(title)}</h2>
      <p><strong>{safe(count)}</strong></p>
    </section>
    """


def build_alerts(db_ok: bool, counts: dict[str, int | str]) -> list[str]:
    alerts: list[str] = []
    if not db_ok:
        alerts.append("Banco indisponivel para consulta.")
    for name, count in counts.items():
        if isinstance(count, str):
            alerts.append(f"{name}: {count}")
        elif count == 0:
            alerts.append(f"{name}: sem registros carregados.")
    if not alerts:
        alerts.append("Bases principais respondendo com registros carregados.")
    return alerts


def render_alerts(alerts: list[str]) -> str:
    items = "\n".join(f"<li>{safe(alert)}</li>" for alert in alerts)
    return f"""
    <section class="mini-panel">
      <h2>Alertas</h2>
      <ul>{items}</ul>
    </section>
    """


def current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() or "desconhecido"
    except Exception:
        return "desconhecido"
