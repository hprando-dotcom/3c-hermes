from __future__ import annotations

import mimetypes
from pathlib import Path
from html import escape
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, render_error_panel, render_top_list, safe
from hermes.database.models import PublicSource, Publication, Source
from hermes.database.session import get_session
from hermes.services.official_gazette_investigation import InvestigationReport, markdown_to_html, run_official_gazette_investigation
from hermes.services.publication_collection import collect_publications_from_source, inspect_and_store_source

router = APIRouter(tags=["publications-ui"])
REPORTS_DIR = Path("data/reports")
EXPORTS_DIR = Path("data/exports")


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
            return html_page("Investigação HERMES", render_investigation_error(exc, target_url, mission, date_start, date_end, limit))

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
        return html_page("Investigação HERMES", render_investigation_error(exc, source_url, mission, date_start, date_end, limit))


@router.get("/downloads/{filename:path}", include_in_schema=False)
def download_dossier_file(filename: str) -> FileResponse:
    path = resolve_download_path(filename)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


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
    examples = [
        "Obras, contratos e aditivos",
        "Licitações e homologações",
        "Atas de registro de preços",
        "Engenharia, pavimentação e drenagem",
        "Manutenção e conservação",
    ]
    example_buttons = "\n".join(
        f'<button type="button" class="pill mission-example" data-mission="{escape(example)}">{safe(example)}</button>' for example in examples
    )
    return f"""
    <section class="product-shell">
      <header class="site-header">
        <a class="brand" href="/">HERMES</a>
        <span>Agente de investigação de Diários Oficiais</span>
        <nav>
          <a href="/">Início</a>
          <a href="/investigar">Investigar</a>
          <a href="/relatorios">Relatórios</a>
          <a href="/fontes">Fontes</a>
          <a href="/publicacoes">Publicações</a>
          <a href="/status">Status</a>
          <a href="/pmsp?ano=2015&limite=50">Consultas avançadas</a>
        </nav>
      </header>
      <div class="cockpit-hero">
        <p class="eyebrow">Cockpit HERMES</p>
        <h1>Investigue publicações oficiais em minutos.</h1>
        <p class="lead">Cole o link do Diário Oficial ou portal público, informe o período e descreva o que o HERMES deve procurar.</p>
      </div>
      <form action="/investigar" method="post" class="search-form">
        <label class="field-wide">Missão
          <textarea id="mission-text" name="mission" rows="6" placeholder="Procure publicações de obras, engenharia, contratos, licitações, atas de registro de preços, homologações e termos aditivos.">{escape(mission or '')}</textarea>
        </label>
        <label class="field-wide">URL da fonte oficial
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
      <section class="mini-panel">
        <h2>Exemplos rápidos de missão</h2>
        <div class="example-list">{example_buttons}</div>
      </section>
      <p class="notice">O HERMES acessa apenas conteúdo público. Se a fonte exigir login, captcha, JavaScript pesado ou PDF sem texto, o relatório indicará a limitação.</p>
      <script>
        document.querySelectorAll('.mission-example').forEach((button) => {{
          button.addEventListener('click', () => {{
            const input = document.getElementById('mission-text');
            if (input) input.value = button.dataset.mission || '';
          }});
        }});
      </script>
    </section>
    """


def render_gazette_report(report: InvestigationReport) -> str:
    findings = report.findings[:20]
    finding_cards = "\n".join(render_finding_card(finding) for finding in findings)
    if not finding_cards:
        finding_cards = '<p class="empty">Nenhum achado relevante classificado no recorte analisado.</p>'
    evidence_items = "\n".join(f'<li><a href="{escape(link)}" target="_blank" rel="noopener">{safe(link)}</a></li>' for link in report.evidence_links[:30])
    limitation_items = "\n".join(f"<li>{safe(item)}</li>" for item in report.limitations) or '<li class="muted">Nenhuma limitação registrada.</li>'
    return f"""
    <section class="product-shell">
      <header class="site-header">
        <a class="brand" href="/">HERMES</a>
        <span>Dossiê de investigação de Diário Oficial</span>
        <nav>
          <a href="/investigar">Nova investigação</a>
          <a href="/relatorios">Relatórios</a>
          <a href="/status">Status</a>
        </nav>
      </header>
      <div class="topbar">
        <div>
          <p class="eyebrow">Produto gerado</p>
          <h1>Relatório HERMES — Investigação de Diário Oficial</h1>
        </div>
        <a class="button secondary" href="/investigar">Nova investigação</a>
      </div>
      <p class="mission-quote">{safe(report.mission_text)}</p>
      <div class="metrics status-grid">
        <div><span>ID da investigação</span><strong>{safe(report.investigation_id)}</strong></div>
        <div><span>Gerado em</span><strong>{safe(report.generated_at)}</strong></div>
        <div><span>IA</span><strong>{'DeepSeek usado' if report.used_deepseek else 'fallback determinístico'}</strong></div>
        <div><span>Links encontrados</span><strong>{report.links_found}</strong></div>
        <div><span>Documentos analisados</span><strong>{report.documents_analyzed}</strong></div>
        <div><span>Achados</span><strong>{len(report.findings)}</strong></div>
      </div>
      <section class="mini-panel">
        <h2>Status da investigação</h2>
        <p><strong>Fonte:</strong> {safe(report.source_url)}</p>
        <p><strong>Período:</strong> {safe(report.date_start or 'não informado')} a {safe(report.date_end or 'não informado')}</p>
        <p><strong>Estratégia:</strong> {safe(report.strategy)}</p>
      </section>
      <section class="mini-panel product-highlight">
        <h2>Produto gerado pelo HERMES</h2>
        <div class="product-grid">
          {render_download_card("Relatório Executivo", "Baixar relatório Markdown", report.report_markdown_path)}
          {render_download_card("Relatório HTML", "Abrir relatório HTML", report.report_html_path, open_new=True)}
          {render_download_card("Achados Estruturados", "Baixar CSV de achados", report.csv_path)}
          {render_download_card("Dados da Investigação", "Baixar JSON", report.json_path)}
          {render_download_card("Dossiê Completo", "Baixar Dossiê ZIP", report.zip_path)}
        </div>
      </section>
      <section class="mini-panel">
        <h2>Principais achados</h2>
        <div class="finding-grid">{finding_cards}</div>
      </section>
      <div class="grid">
        <section class="mini-panel"><h2>Evidências</h2><ul>{evidence_items or '<li class="muted">Sem evidências.</li>'}</ul></section>
        <section class="mini-panel"><h2>Limitações</h2><ul>{limitation_items}</ul></section>
        <section class="mini-panel"><h2>Métricas</h2><ul>{render_metric_items(report.metrics)}</ul></section>
      </div>
      <section class="mini-panel">
        <h2>Relatório formatado</h2>
        <div class="report-body">{markdown_to_html(report.markdown)}</div>
      </section>
    </section>
    """


def render_investigation_error(
    exc: Exception,
    source_url: str | None,
    mission: str | None,
    date_start: str | None,
    date_end: str | None,
    limit: int,
) -> str:
    message = str(exc) or exc.__class__.__name__
    probable_step = "Validação da URL" if isinstance(exc, ValueError) else "Acesso à fonte ou extração do conteúdo público"
    suggestion = "Revise a URL e tente novamente. Se a fonte exigir login, captcha ou JavaScript pesado, use outra página pública ou registre a limitação no dossiê."
    return f"""
    <section class="product-shell">
      <header class="site-header">
        <a class="brand" href="/">HERMES</a>
        <span>Investigação de Diários Oficiais</span>
        <nav><a href="/investigar">Tentar novamente</a><a href="/status">Status</a></nav>
      </header>
      <section class="panel">
        <p class="eyebrow">Investigação interrompida</p>
        <h1>Não foi possível concluir a investigação.</h1>
        <p class="error">{safe(message)}</p>
        <div class="grid">
          <section class="mini-panel"><h2>Etapa provável</h2><p>{safe(probable_step)}</p></section>
          <section class="mini-panel"><h2>Sugestão</h2><p>{safe(suggestion)}</p></section>
          <section class="mini-panel"><h2>Próximo passo</h2><p><a href="/investigar">Abrir o cockpit e tentar novamente</a></p></section>
        </div>
      </section>
      {render_investigation_form(source_url, mission, date_start, date_end, limit)}
    </section>
    """


def render_finding_card(finding: Any) -> str:
    matched_terms = ", ".join(finding.matched_terms or []) or "-"
    return f"""
    <article class="finding-card">
      <div class="finding-card-header">
        <h3>{safe(finding.title)}</h3>
        <span class="badge">score {safe(finding.score)}</span>
      </div>
      <p class="muted">{safe(finding.date or 'data desconhecida')} · {safe(finding.event_type)} · {safe(finding.natureza)}</p>
      <dl>
        <dt>Órgão</dt><dd>{safe(finding.agency)}</dd>
        <dt>Empresa</dt><dd>{safe(finding.company_name)}</dd>
        <dt>Processo</dt><dd>{safe(finding.process_number)}</dd>
        <dt>Contrato</dt><dd>{safe(finding.contract_number)}</dd>
        <dt>Valor</dt><dd>{safe(finding.value_text)}</dd>
        <dt>Termos</dt><dd>{safe(matched_terms)}</dd>
      </dl>
      <p>{safe(finding.summary or finding.object_text)}</p>
      <blockquote>{safe(finding.snippet)}</blockquote>
      <a class="button secondary" href="{escape(finding.link)}" target="_blank" rel="noopener">Abrir fonte</a>
    </article>
    """


def render_download_card(title: str, action: str, path: str | None, *, open_new: bool = False) -> str:
    filename = Path(path or "").name
    if not filename:
        return f"""
        <article class="download-card">
          <strong>{safe(title)}</strong>
          <span class="muted">Arquivo indisponível.</span>
        </article>
        """
    target = " target=\"_blank\" rel=\"noopener\"" if open_new else ""
    return f"""
    <article class="download-card">
      <strong>{safe(title)}</strong>
      <span>{safe(filename)}</span>
      <a class="button" href="/downloads/{escape(filename)}"{target}>{safe(action)}</a>
    </article>
    """


def resolve_download_path(filename: str) -> Path:
    raw = filename or ""
    if "\\" in raw or "/" in raw or ".." in raw or raw.startswith(".") or Path(raw).is_absolute():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    if raw.lower() == ".env" or raw.lower().endswith(".env"):
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
    for directory in (REPORTS_DIR, EXPORTS_DIR):
        root = directory.resolve()
        candidate = (directory / raw).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")


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
