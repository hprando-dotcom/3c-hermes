from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, safe
from hermes.database.session import get_session
from hermes.services.mission_intelligence import default_suggestions, investigate_mission

router = APIRouter(tags=["missions"])
EXPORTS_DIR = Path("data/exports")


@router.get("/missao", response_class=HTMLResponse, include_in_schema=False)
def mission_page(
    q: str = Query(default="", description="Missao em linguagem natural."),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    mission = q.strip()
    if not mission:
        return html_page("Missao HERMES", render_empty_mission())

    result = investigate_mission(session, mission)
    return html_page("Resultado da missao", render_mission_result(result))


@router.get("/relatorios", response_class=HTMLResponse, include_in_schema=False)
def reports_page() -> HTMLResponse:
    reports = load_dossier_history()
    if reports:
        cards = "\n".join(render_dossier_card(report) for report in reports)
    else:
        cards = """
        <section class="mini-panel">
          <h2>Nenhum dossiê gerado ainda.</h2>
          <p class="empty">Comece uma investigação para gerar o primeiro relatório executivo, achados estruturados e pacote ZIP.</p>
          <a class="button" href="/investigar">Começar investigação</a>
        </section>
        """
    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Relatórios HERMES</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="muted">Histórico dos dossiês gerados pelo cockpit de investigação de Diários Oficiais.</p>
      <div class="module-grid">{cards}</div>
    </section>
    """
    return html_page("Relatorios HERMES", body)


def load_dossier_history() -> list[dict[str, Any]]:
    if not EXPORTS_DIR.exists():
        return []
    reports: list[dict[str, Any]] = []
    for path in EXPORTS_DIR.glob("hermes_diario_*.json"):
        if path.name.endswith("_summary.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict) or not payload.get("investigation_id"):
            continue
        payload["_json_file"] = str(path)
        reports.append(payload)
    reports.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return reports


def render_dossier_card(report: dict[str, Any]) -> str:
    investigation_id = str(report.get("investigation_id") or "dossie")
    generated_at = report.get("generated_at") or "data não informada"
    mission = report.get("mission_text") or "-"
    source_url = report.get("source_url") or "-"
    date_start = report.get("date_start") or "não informado"
    date_end = report.get("date_end") or "não informado"
    totals = report.get("totals") if isinstance(report.get("totals"), dict) else {}
    findings_count = totals.get("findings", len(report.get("findings") or []))
    deepseek = "DeepSeek usado" if report.get("deepseek_used") or report.get("used_deepseek") else "fallback determinístico"
    return f"""
    <article class="module-card dossier-card">
      <strong>{safe(investigation_id)}</strong>
      <span>{safe(generated_at)} · {safe(findings_count)} achados · {safe(deepseek)}</span>
      <p><strong>Missão:</strong> {safe(mission)}</p>
      <p><strong>Fonte:</strong> {safe(source_url)}</p>
      <p><strong>Período:</strong> {safe(date_start)} a {safe(date_end)}</p>
      <div class="actions">
        {render_dossier_link("Abrir relatório HTML", report.get("report_html_path"), open_new=True)}
        {render_dossier_link("Baixar Markdown", report.get("report_markdown_path") or report.get("markdown_path"))}
        {render_dossier_link("Baixar CSV", report.get("csv_path"))}
        {render_dossier_link("Baixar JSON", report.get("json_path"))}
        {render_dossier_link("Baixar Dossiê ZIP", report.get("zip_path"))}
      </div>
    </article>
    """


def render_dossier_link(label: str, path: Any, *, open_new: bool = False) -> str:
    filename = Path(str(path or "")).name
    if not filename:
        return ""
    target = " target=\"_blank\" rel=\"noopener\"" if open_new else ""
    return f'<a class="button secondary" href="/downloads/{escape(filename)}"{target}>{safe(label)}</a>'


def render_empty_mission() -> str:
    suggestions = render_suggestion_links(default_suggestions())
    return f"""
    <section class="panel">
      <div class="topbar">
        <h1>Missao HERMES</h1>
        <a class="button secondary" href="/">Voltar</a>
      </div>
      <p class="empty">Escreva uma missao para o HERMES investigar.</p>
      <div class="example-list">{suggestions}</div>
    </section>
    """


def render_mission_result(result: dict[str, Any]) -> str:
    analysis = result["analysis"]
    bases = result["bases"] or ["Nenhuma base consultada"]
    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Resultado da missao</h1>
        <a class="button secondary" href="/">Nova missao</a>
      </div>
      <p class="mission-quote">{safe(result["mission"])}</p>
      <div class="metrics">
        <div><span>Bases consultadas</span><strong>{len(result["bases"])}</strong></div>
        <div><span>Temas</span><strong>{safe(", ".join(analysis.themes) if analysis.themes else "a definir")}</strong></div>
        <div><span>Evidencias</span><strong>{len(result["records"])}</strong></div>
      </div>
      <section class="mini-panel">
        <h2>Resumo executivo</h2>
        <p>{safe(result["summary"])}</p>
      </section>
      <div class="grid">
        {render_list_panel("Dados consultados", bases)}
        {render_list_panel("Principais achados", result["findings"])}
        {render_list_panel("Alertas de qualidade", result["quality_alerts"] or ["Nenhum alerta relevante no recorte consultado."])}
      </div>
      {render_rankings(result["rankings"])}
      {render_records(result["records"])}
      {render_list_panel("Proximas perguntas sugeridas", result["next_questions"], as_links=True)}
      {render_errors(result["errors"])}
    </section>
    """
    return body


def render_suggestion_links(suggestions: list[str]) -> str:
    return "\n".join(
        f'<a class="pill" href="/missao?q={escape(suggestion).replace(" ", "%20")}">{safe(suggestion)}</a>'
        for suggestion in suggestions
    )


def render_list_panel(title: str, items: list[Any], *, as_links: bool = False) -> str:
    if not items:
        rendered = '<li class="muted">Sem dados.</li>'
    elif as_links:
        rendered = "\n".join(
            f'<li><a href="/missao?q={escape(str(item)).replace(" ", "%20")}">{safe(item)}</a></li>' for item in items
        )
    else:
        rendered = "\n".join(f"<li>{safe(item)}</li>" for item in items)
    return f"""
    <section class="mini-panel">
      <h2>{safe(title)}</h2>
      <ul>{rendered}</ul>
    </section>
    """


def render_rankings(rankings: dict[str, list[tuple[str, Any]]]) -> str:
    if not rankings:
        return ""
    panels = []
    for title, rows in rankings.items():
        if not rows:
            panels.append(render_list_panel(title, ["Sem registros para ranking."]))
            continue
        items = "\n".join(f"<li><span>{safe(label)}</span><strong>{safe(value)}</strong></li>" for label, value in rows)
        panels.append(
            f"""
            <section class="mini-panel">
              <h2>{safe(title)}</h2>
              <ol>{items}</ol>
            </section>
            """
        )
    return f'<div class="grid">{"".join(panels)}</div>'


def render_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return '<section class="mini-panel"><h2>Evidencias</h2><p class="empty">Nenhum registro relevante foi retornado para este recorte.</p></section>'
    rows = "\n".join(
        f"""
        <tr>
          <td>{safe(record.get("source"))}</td>
          <td>{safe(record.get("orgao"))}</td>
          <td>{safe(record.get("evento"))}</td>
          <td>{safe(record.get("processo"))}</td>
          <td>{safe(record.get("contrato"))}</td>
          <td>{safe(record.get("fornecedor"))}</td>
          <td>{safe(record.get("valor"))}</td>
          <td class="object-cell">{safe(record.get("descricao"))}</td>
        </tr>
        """
        for record in records
    )
    return f"""
    <section class="mini-panel">
      <h2>Evidencias</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Fonte</th><th>Orgao</th><th>Evento</th><th>Processo</th><th>Contrato</th><th>Fornecedor</th><th>Valor</th><th>Descricao</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
    """


def render_errors(errors: list[str]) -> str:
    if not errors:
        return ""
    return render_list_panel("Observacoes tecnicas", errors)
