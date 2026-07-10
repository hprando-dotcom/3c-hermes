from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, render_error_panel, render_top_list, safe
from hermes.database.models import PublicSource, Publication, Source
from hermes.database.session import get_session
from hermes.services.publication_collection import collect_publications_from_source, inspect_and_store_source

router = APIRouter(tags=["publications-ui"])


@router.get("/investigar", response_class=HTMLResponse, include_in_schema=False)
def investigate_source_page(
    url: str | None = Query(default=None),
    coletar: bool = Query(default=False),
    limite: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if not url:
        return html_page("Investigar fonte oficial", render_investigation_form())

    try:
        if coletar:
            collection = collect_publications_from_source(url, session=session, limit=limite)
            inspection = collection.get("inspection") or {}
            body = render_collection_result(url, collection)
        else:
            stored = inspect_and_store_source(url, session=session)
            inspection = stored["inspection"]
            body = render_inspection_result(inspection)
    except SQLAlchemyError as exc:
        return html_page("Investigar fonte oficial", render_error_panel("Nao foi possivel registrar a fonte oficial.", exc))
    except Exception as exc:
        body = f"""
        <section class="panel">
          <div class="topbar">
            <h1>Investigacao de fonte oficial</h1>
            <a class="button secondary" href="/">HERMES</a>
          </div>
          <p class="error">Falha ao investigar a fonte.</p>
          <p class="muted">{safe(exc.__class__.__name__)}: {safe(exc)}</p>
          {render_investigation_form(url)}
        </section>
        """
    return html_page("Investigar fonte oficial", body)


@router.get("/fontes", response_class=HTMLResponse, include_in_schema=False)
def public_sources_page(
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        rows = list(session.scalars(select(PublicSource).order_by(desc(PublicSource.last_inspected_at)).limit(limite)))
        total = int(session.scalar(select(func.count()).select_from(PublicSource)) or 0)
    except SQLAlchemyError as exc:
        return html_page("Fontes oficiais", render_error_panel("Nao foi possivel consultar `public_sources`.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Fontes oficiais investigadas</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p><strong>Total:</strong> {total}</p>
      {render_sources_table(rows)}
    </section>
    """
    return html_page("Fontes oficiais", body)


@router.get("/publicacoes", response_class=HTMLResponse, include_in_schema=False)
def publications_page(
    termo: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        conditions = []
        if termo:
            term = f"%{termo.strip()}%"
            conditions.append(Publication.object_description.ilike(term) | Publication.clean_text.ilike(term))
        if tipo:
            conditions.append(Publication.publication_type == tipo)
        rows = list(
            session.scalars(
                select(Publication)
                .where(*conditions)
                .order_by(desc(Publication.collected_at))
                .limit(limite)
            )
        )
        total = int(session.scalar(select(func.count()).select_from(Publication).where(*conditions)) or 0)
    except SQLAlchemyError as exc:
        return html_page("Publicacoes oficiais", render_error_panel("Nao foi possivel consultar `publications`.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Publicacoes oficiais coletadas</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <form action="/publicacoes" method="get" class="summary-form">
        <label>Termo <input name="termo" value="{escape(termo or '')}" placeholder="Ex.: edital"></label>
        <label>Tipo <input name="tipo" value="{escape(tipo or '')}" placeholder="pdf, html, endpoint"></label>
        <label>Limite <input type="number" name="limite" value="{limite}" min="1" max="500"></label>
        <button type="submit">Filtrar</button>
      </form>
      <p><strong>Total encontrado:</strong> {total}</p>
      {render_publications_table(rows)}
    </section>
    """
    return html_page("Publicacoes oficiais", body)


@router.get("/publicacoes/resumo", response_class=HTMLResponse, include_in_schema=False)
def publications_summary_page(session: Session = Depends(get_session)) -> HTMLResponse:
    try:
        total_sources = int(session.scalar(select(func.count()).select_from(PublicSource)) or 0)
        total_publications = int(session.scalar(select(func.count()).select_from(Publication)) or 0)
        without_links = int(session.scalar(select(func.count()).select_from(Publication).where(Publication.links == [])) or 0)
        top_types = top_counts(session, Publication.publication_type, Publication)
        top_sources = top_source_counts(session)
    except SQLAlchemyError as exc:
        return html_page("Resumo publicacoes", render_error_panel("Nao foi possivel gerar o resumo de publicacoes.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Resumo de publicacoes oficiais</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <div class="metrics">
        <div><span>Fontes</span><strong>{total_sources}</strong></div>
        <div><span>Publicacoes</span><strong>{total_publications}</strong></div>
        <div><span>Sem links</span><strong>{without_links}</strong></div>
      </div>
      <div class="grid">
        {render_top_list("Tipos", top_types)}
        {render_top_list("Fontes", top_sources)}
        {render_top_list("Alertas", [("Fontes com erro devem ser reinspecionadas", 1)])}
      </div>
    </section>
    """
    return html_page("Resumo publicacoes", body)


def render_investigation_form(url: str | None = None) -> str:
    return f"""
    <section class="panel">
      <div class="topbar">
        <h1>Investigar fonte oficial</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="muted">Informe uma pagina oficial. O HERMES procura links, PDFs, endpoints e publicacoes candidatas.</p>
      <form action="/investigar" method="get" class="mission-form">
        <label>URL da fonte oficial
          <input name="url" value="{escape(url or '')}" placeholder="https://www.prefeitura.sp.gov.br/...">
        </label>
        <button type="submit">Investigar fonte oficial</button>
      </form>
    </section>
    """


def render_inspection_result(inspection: dict[str, Any]) -> str:
    candidates = inspection.get("publication_candidates", [])
    endpoints = inspection.get("endpoint_candidates", [])
    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Fonte oficial investigada</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="mission-quote">{safe(inspection.get("url"))}</p>
      <div class="metrics">
        <div><span>Links</span><strong>{len(inspection.get("links", []))}</strong></div>
        <div><span>PDFs</span><strong>{len(inspection.get("pdf_links", []))}</strong></div>
        <div><span>Candidatas</span><strong>{len(candidates)}</strong></div>
      </div>
      <div class="actions">
        <a class="button" href="/investigar?{build_collect_query(inspection.get('url'))}">Coletar publicacoes</a>
        <a class="button secondary" href="/fontes">Fontes investigadas</a>
        <a class="button secondary" href="/publicacoes">Publicacoes</a>
      </div>
      <div class="grid">
        {render_item_list("Endpoints detectados", [item.get("url") for item in endpoints[:10]])}
        {render_item_list("PDFs detectados", [item.get("url") for item in inspection.get("pdf_links", [])[:10]])}
        {render_item_list("Publicacoes candidatas", [item.get("title") or item.get("url") for item in candidates[:10]])}
      </div>
    </section>
    """
    return body


def render_collection_result(url: str, collection: dict[str, Any]) -> str:
    return f"""
    <section class="panel">
      <div class="topbar">
        <h1>Coleta de publicacoes</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="mission-quote">{safe(url)}</p>
      <div class="metrics">
        <div><span>Encontradas</span><strong>{collection.get('fetched')}</strong></div>
        <div><span>Inseridas</span><strong>{collection.get('inserted')}</strong></div>
        <div><span>Atualizadas</span><strong>{collection.get('updated')}</strong></div>
      </div>
      {render_item_list("Erros", collection.get("errors") or ["Nenhum erro registrado."])}
      <div class="actions">
        <a class="button secondary" href="/publicacoes">Ver publicacoes</a>
        <a class="button secondary" href="/publicacoes/resumo">Resumo</a>
      </div>
    </section>
    """


def render_sources_table(rows: list[PublicSource]) -> str:
    if not rows:
        return '<p class="empty">Nenhuma fonte oficial investigada ainda.</p>'
    body = "\n".join(
        f"""
        <tr>
          <td>{safe(row.title)}</td>
          <td>{safe(row.normalized_url)}</td>
          <td>{safe(row.status)}</td>
          <td>{safe(row.last_status_code)}</td>
          <td>{safe(row.last_inspected_at)}</td>
        </tr>
        """
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr><th>Titulo</th><th>URL</th><th>Status</th><th>HTTP</th><th>Inspecionada em</th></tr></thead><tbody>{body}</tbody></table></div>"


def render_publications_table(rows: list[Publication]) -> str:
    if not rows:
        return '<p class="empty">Nenhuma publicacao coletada ainda.</p>'
    body = "\n".join(
        f"""
        <tr>
          <td>{safe(row.source_name)}</td>
          <td>{safe(row.publication_type)}</td>
          <td>{safe(row.year)}</td>
          <td>{safe(row.object_description)}</td>
          <td>{render_links(row.links)}</td>
        </tr>
        """
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr><th>Fonte</th><th>Tipo</th><th>Ano</th><th>Publicacao</th><th>Links</th></tr></thead><tbody>{body}</tbody></table></div>"


def render_links(links: Any) -> str:
    if not links:
        return '<span class="muted">-</span>'
    first = links[0] if isinstance(links, list) else None
    if not isinstance(first, dict) or not first.get("url"):
        return '<span class="muted">-</span>'
    return f'<a href="{escape(first["url"])}" target="_blank" rel="noopener">abrir</a>'


def build_collect_query(url: Any) -> str:
    return urlencode({"url": str(url or ""), "coletar": "true"})


def render_item_list(title: str, items: list[Any]) -> str:
    rendered = "\n".join(f"<li>{safe(item)}</li>" for item in items) if items else '<li class="muted">Sem itens.</li>'
    return f"<section class=\"mini-panel\"><h2>{safe(title)}</h2><ul>{rendered}</ul></section>"


def top_counts(session: Session, field: Any, model: Any) -> list[tuple[str, int]]:
    total = func.count().label("total")
    rows = session.execute(
        select(field, total)
        .select_from(model)
        .where(field.is_not(None), field != "")
        .group_by(field)
        .order_by(desc(total))
        .limit(10)
    )
    return [(str(value), int(count)) for value, count in rows]


def top_source_counts(session: Session) -> list[tuple[str, int]]:
    total = func.count(Publication.id).label("total")
    rows = session.execute(
        select(Source.name, total)
        .join(Publication, Publication.source_id == Source.id)
        .group_by(Source.name)
        .order_by(desc(total))
        .limit(10)
    )
    return [(str(value), int(count)) for value, count in rows]
