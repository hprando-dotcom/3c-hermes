from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, safe
from hermes.database.session import get_session
from hermes.services.mission_intelligence import default_suggestions, investigate_mission

router = APIRouter(tags=["missions"])


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
    reports = [
        {
            "title": "Resumo PMSP",
            "description": "Visao consolidada da base PMSP Licitacoes carregada.",
            "href": "/pmsp/resumo?ano=2015",
        },
        {
            "title": "Engenharia e manutencao PMSP",
            "description": "Missao pronta para obras, manutencao, reformas e engenharia.",
            "href": "/missao?q=obras%20e%20manutencao%20em%20Sao%20Paulo",
        },
        {
            "title": "Fornecedores PMSP",
            "description": "Ranking inicial de fornecedores recorrentes em contratos publicos.",
            "href": "/missao?q=fornecedores%20recorrentes%20em%20contratos%20publicos",
        },
        {
            "title": "Resumo TCE-SP",
            "description": "Totais, rankings e alertas das tabelas TCE-SP persistidas.",
            "href": "/tcesp/resumo?ano=2015",
        },
    ]
    cards = "\n".join(
        f"""
        <a class="module-card" href="{escape(report['href'])}">
          <strong>{safe(report['title'])}</strong>
          <span>{safe(report['description'])}</span>
        </a>
        """
        for report in reports
    )
    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Relatorios</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="muted">Atalhos iniciais para investigacoes recorrentes. A persistencia de relatorios entra em etapa futura.</p>
      <div class="module-grid">{cards}</div>
    </section>
    """
    return html_page("Relatorios HERMES", body)


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
