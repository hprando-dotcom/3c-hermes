from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, render_error_panel, render_top_list, safe
from hermes.database.models import PublicSource, Publication, Source
from hermes.database.session import get_session
from hermes.services.official_gazette_investigation import InvestigationReport, run_official_gazette_investigation
from hermes.services.publication_collection import collect_publications_from_source, inspect_and_store_source

router = APIRouter(tags=["publications-ui"])


@router.get("/investigar", response_class=HTMLResponse, include_in_schema=False)
def investigate_source_page(
    url: str | None = Query(default=None),
    source_url: str | None = Query(default=None),
    mission: str | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    coletar: bool = Query(default=False),
    limite: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    target_url = source_url or url
    if not target_url:
        return html_page("Investigar Diário Oficial", render_investigation_form())

    if mission:
        try:
            report = run_official_gazette_investigation(
                target_url,
                mission,
                date_start,
                date_end,
                limit=limit,
            )
            return html_page("Investigação HERMES", render_gazette_report(report))
        except Exception as exc:
            body = f"""
            <section class="panel">
              <div class="topbar">
                <h1>Investigação de Diário Oficial</h1>
                <a class="button secondary" href="/">HERMES</a>
              </div>
              <p class="error">Falha ao executar a investigação.</p>
              <p class="muted">{safe(exc.__class__.__name__)}: {safe(exc)}</p>
              {render_investigation_form(target_url, mission, date_start, date_end, limit)}
            </section>
            """
            return html_page("Investigação HERMES", body)

    try:
        if coletar:
            collection = collect_publications_from_source(target_url, session=session, limit=limite)
            inspection = collection.get("inspection") or {}
            body = render_collection_result(target_url, collection)
        else:
            stored = inspect_and_store_source(target_url, session=session)
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


@router.post("/investigar", response_class=HTMLResponse, include_in_schema=False)
async def investigate_source_post(request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode("utf-8", errors="ignore"), keep_blank_values=True)
    source_url = first_form_value(form, "source_url") or first_form_value(form, "url") or ""
    mission = first_form_value(form, "mission") or ""
    date_start = first_form_value(form, "date_start") or None
    date_end = first_form_value(form, "date_end") or None
    limit = int(first_form_value(form, "limit") or 50)
    if not source_url or not mission:
        return html_page("Investigar Diário Oficial", render_investigation_form(source_url or None, mission or None, date_start, date_end, limit))
    try:
        report = run_official_gazette_investigation(source_url, mission, date_start, date_end, limit=limit)
        return html_page("Investigação HERMES", render_gazette_report(report))
    except Exception as exc:
        body = f"""
        <section class="panel">
          <div class="topbar">
            <h1>Investigação de Diário Oficial</h1>
            <a class="button secondary" href="/">HERMES</a>
          </div>
          <p class="error">Falha ao executar a investigação.</p>
          <p class="muted">{safe(exc.__class__.__name__)}: {safe(exc)}</p>
          {render_investigation_form(source_url, mission, date_start, date_end, limit)}
        </section>
        """
        return html_page("Investigação HERMES", body)


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


def render_investigation_form(
    source_url: str | None = None,
    mission: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    limit: int = 50,
) -> str:
    return f"""
    <section class="panel">
      <div class="topbar">
        <h1>Investigar Diário Oficial</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="muted">Informe a missão, a URL do Diário Oficial ou portal público e o período. O HERMES coleta publicações, classifica os atos e gera relatório Markdown com evidências.</p>
      <form action="/investigar" method="post" class="search-form">
        <label>Missão
          <textarea name="mission" rows="4" placeholder="Ex.: obras contratos aditivos engenharia">{escape(mission or '')}</textarea>
        </label>
        <label>URL da fonte oficial
          <input name="source_url" value="{escape(source_url or '')}" placeholder="https://www.prefeitura.sp.gov.br/...">
        </label>
        <label>Data inicial
          <input type="date" name="date_start" value="{escape(date_start or '')}">
        </label>
        <label>Data final
          <input type="date" name="date_end" value="{escape(date_end or '')}">
        </label>
        <label>Limite
          <input type="number" name="limit" value="{limit}" min="1" max="200">
        </label>
        <button type="submit">Investigar Diário Oficial</button>
      </form>
    </section>
    """


def render_gazette_report(report: InvestigationReport) -> str:
    findings = report.findings[:20]
    findings_rows = "\n".join(
        f"""
        <tr>
          <td>{safe(finding.title)}</td>
          <td>{safe(finding.date or 'data desconhecida')}</td>
          <td>{safe(finding.event_type)}</td>
          <td>{safe(finding.natureza)}</td>
          <td>{safe(finding.score)}</td>
          <td>{safe(finding.agency)}</td>
          <td>{safe(finding.company_name)}</td>
          <td><a href="{escape(finding.link)}" target="_blank" rel="noopener">evidência</a></td>
        </tr>
        """
        for finding in findings
    )
    if not findings_rows:
        findings_rows = '<tr><td colspan="8"><span class="muted">Nenhum achado relevante classificado.</span></td></tr>'
    evidence_items = "\n".join(f'<li><a href="{escape(link)}" target="_blank" rel="noopener">{safe(link)}</a></li>' for link in report.evidence_links[:30])
    limitation_items = "\n".join(f"<li>{safe(item)}</li>" for item in report.limitations) or '<li class="muted">Nenhuma limitação registrada.</li>'
    markdown_preview = "\n".join(report.markdown.splitlines()[:80])
    return f"""
    <section class="panel">
      <div class="topbar">
        <h1>Relatório HERMES — Investigação de Diário Oficial</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="mission-quote">{safe(report.mission_text)}</p>
      <div class="metrics">
        <div><span>Links encontrados</span><strong>{report.links_found}</strong></div>
        <div><span>Documentos analisados</span><strong>{report.documents_analyzed}</strong></div>
        <div><span>Achados</span><strong>{len(report.findings)}</strong></div>
      </div>
      <section class="mini-panel">
        <h2>Fonte e período</h2>
        <p><strong>Fonte:</strong> {safe(report.source_url)}</p>
        <p><strong>Período:</strong> {safe(report.date_start or 'não informado')} a {safe(report.date_end or 'não informado')}</p>
        <p><strong>Estratégia:</strong> {safe(report.strategy)}</p>
        <p><strong>Relatório Markdown:</strong> {safe(report.markdown_path)}</p>
        <p><strong>IA:</strong> {'DeepSeek usado' if report.used_deepseek else 'fallback determinístico'}</p>
      </section>
      <section class="mini-panel">
        <h2>Principais achados</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Título</th><th>Data</th><th>Tipo</th><th>Natureza</th><th>Score</th><th>Órgão</th><th>Empresa</th><th>Link</th></tr></thead>
            <tbody>{findings_rows}</tbody>
          </table>
        </div>
      </section>
      <div class="grid">
        <section class="mini-panel"><h2>Evidências</h2><ul>{evidence_items or '<li class="muted">Sem evidências.</li>'}</ul></section>
        <section class="mini-panel"><h2>Limitações</h2><ul>{limitation_items}</ul></section>
        <section class="mini-panel"><h2>Métricas</h2><ul>{render_metric_items(report.metrics)}</ul></section>
      </div>
      <section class="mini-panel">
        <h2>Prévia do Markdown</h2>
        <pre>{escape(markdown_preview)}</pre>
      </section>
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


def first_form_value(form: dict[str, list[str]], key: str) -> str | None:
    values = form.get(key)
    if not values:
        return None
    return values[0]


def render_item_list(title: str, items: list[Any]) -> str:
    rendered = "\n".join(f"<li>{safe(item)}</li>" for item in items) if items else '<li class="muted">Sem itens.</li>'
    return f"<section class=\"mini-panel\"><h2>{safe(title)}</h2><ul>{rendered}</ul></section>"


def render_metric_items(metrics: dict[str, Any]) -> str:
    return "\n".join(f"<li>{safe(key)}: <strong>{safe(value)}</strong></li>" for key, value in metrics.items())


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
