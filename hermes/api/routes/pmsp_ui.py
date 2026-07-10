from __future__ import annotations

from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.database.models import PmspLicitacao
from hermes.database.session import get_session

router = APIRouter(tags=["pmsp-ui"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return html_page(
        "HERMES - Agente de Inteligencia sobre Publicacoes Publicas",
        """
        <section class="hero">
          <p class="eyebrow">Agente de Inteligencia sobre Publicacoes Publicas</p>
          <h1>HERMES</h1>
          <p class="lead">O HERMES investiga publicacoes publicas para voce, cruza fontes oficiais e entrega achados, alertas e relatorios acionaveis.</p>
          <form action="/missao" method="get" class="mission-form">
            <label>O que voce quer que o HERMES investigue?
              <textarea name="q" rows="4" placeholder="Ex.: obras e manutencao em Sao Paulo"></textarea>
            </label>
            <button type="submit">Investigar</button>
          </form>
          <form action="/investigar" method="get" class="mission-form">
            <label>URL da fonte oficial
              <input name="url" placeholder="https://www.prefeitura.sp.gov.br/...">
            </label>
            <button type="submit">Investigar fonte oficial</button>
          </form>
          <div class="example-list">
            <a class="pill" href="/missao?q=obras%20e%20manutencao%20em%20Sao%20Paulo">Obras e manutencao em Sao Paulo</a>
            <a class="pill" href="/missao?q=fornecedores%20recorrentes%20em%20contratos%20publicos">Fornecedores recorrentes</a>
            <a class="pill" href="/missao?q=movimentacoes%20de%20saude">Movimentacoes de saude</a>
            <a class="pill" href="/missao?q=despesas%20municipais%20no%20TCE-SP">Despesas municipais no TCE-SP</a>
            <a class="pill" href="/missao?q=orgaos%20mais%20ativos">Orgaos mais ativos</a>
            <a class="pill" href="/investigar">Investigar uma fonte oficial</a>
          </div>
          <div class="quick-actions">
            <a class="button secondary" href="/relatorios">Relatorios</a>
            <a class="button secondary" href="/fontes">Fontes</a>
            <a class="button secondary" href="/publicacoes">Publicacoes</a>
            <a class="button secondary" href="/status">Status</a>
            <a class="button secondary" href="/docs">OpenAPI Docs</a>
          </div>
        </section>
        <section class="module-grid">
          <a class="module-card" href="/missao?q=obras%20e%20manutencao%20em%20Sao%20Paulo">
            <strong>Missoes recentes</strong>
            <span>Reabra investigacoes frequentes sobre obras, manutencao, fornecedores, saude e orgaos ativos.</span>
          </a>
          <a class="module-card" href="/relatorios">
            <strong>Relatorios</strong>
            <span>Atalhos para resumos executivos e investigacoes prontas.</span>
          </a>
          <a class="module-card" href="/status">
            <strong>Alertas</strong>
            <span>Qualidade das bases, lacunas e sinais operacionais do sistema.</span>
          </a>
          <a class="module-card" href="/status">
            <strong>Fontes monitoradas</strong>
            <span>PMSP, TCE-SP e fontes oficiais inspecionadas por URL pelo agente investigador.</span>
          </a>
          <a class="module-card" href="/publicacoes/resumo">
            <strong>Publicacoes oficiais</strong>
            <span>Resumo das publicacoes coletadas por scraping, PDFs e endpoints detectados.</span>
          </a>
          <a class="module-card" href="/status">
            <strong>Status do sistema</strong>
            <span>API, banco, totais carregados e alertas operacionais em uma visao unica.</span>
          </a>
        </section>
        <section class="panel">
          <h2>Modo exploratorio avancado</h2>
          <p class="muted">Consultas tecnicas continuam disponiveis para auditoria, validacao e exploracao manual das bases.</p>
          <div class="actions">
            <a class="button secondary" href="/pmsp?ano=2015&limite=50">Consulta avancada PMSP</a>
            <a class="button secondary" href="/tcesp">Consulta avancada TCE-SP</a>
            <a class="button secondary" href="/pmsp/resumo?ano=2015">Resumo PMSP</a>
            <a class="button secondary" href="/tcesp/resumo?ano=2015">Resumo TCE-SP</a>
          </div>
        </section>
        """,
    )


@router.get("/pmsp", response_class=HTMLResponse, include_in_schema=False)
def search_pmsp(
    ano: int = Query(default=2015),
    orgao: str | None = Query(default=None),
    termo: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    criteria = build_criteria(ano=ano, orgao=orgao, termo=termo, limite=limite)
    try:
        conditions = [PmspLicitacao.ano == ano]
        if orgao:
            conditions.append(PmspLicitacao.orgao.ilike(f"%{orgao.strip()}%"))
        if termo:
            conditions.append(PmspLicitacao.objeto.ilike(f"%{termo.strip()}%"))

        total = session.scalar(select(func.count()).select_from(PmspLicitacao).where(*conditions)) or 0
        rows = list(
            session.scalars(
                select(PmspLicitacao)
                .where(*conditions)
                .order_by(PmspLicitacao.data_publicacao.desc().nullslast(), PmspLicitacao.id.desc())
                .limit(limite)
            )
        )
    except SQLAlchemyError as exc:
        return html_page(
            "Consulta PMSP",
            render_error_panel("Não foi possível consultar `pmsp_licitacoes`.", exc),
        )

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Consulta avancada PMSP</h1>
        <a class="button secondary" href="/">Nova busca</a>
      </div>
      <p class="muted">Critérios: {escape(criteria)}</p>
      <p><strong>Total encontrado:</strong> {total}</p>
      {render_pmsp_table(rows)}
    </section>
    """
    return html_page("Consulta PMSP", body)


@router.get("/pmsp/resumo", response_class=HTMLResponse, include_in_schema=False)
def pmsp_summary(
    ano: int = Query(default=2015),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        total = session.scalar(
            select(func.count()).select_from(PmspLicitacao).where(PmspLicitacao.ano == ano)
        ) or 0
        missing_fornecedor = session.scalar(
            select(func.count())
            .select_from(PmspLicitacao)
            .where(
                PmspLicitacao.ano == ano,
                or_(PmspLicitacao.fornecedor.is_(None), PmspLicitacao.fornecedor == ""),
            )
        ) or 0
        suspicious_orgao = session.scalar(
            select(func.count())
            .select_from(PmspLicitacao)
            .where(
                PmspLicitacao.ano == ano,
                PmspLicitacao.orgao.ilike("%,%"),
                or_(
                    PmspLicitacao.modalidade.is_(None),
                    PmspLicitacao.numero_processo.is_(None),
                    PmspLicitacao.objeto.is_(None),
                ),
            )
        ) or 0

        top_orgaos = top_counts(session, PmspLicitacao.orgao, ano)
        top_modalidades = top_counts(session, PmspLicitacao.modalidade, ano)
        top_fornecedores = top_counts(session, PmspLicitacao.fornecedor, ano)
    except SQLAlchemyError as exc:
        return html_page(
            "Resumo PMSP",
            render_error_panel("Não foi possível gerar o resumo de `pmsp_licitacoes`.", exc),
        )

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Resumo Geral PMSP</h1>
        <a class="button secondary" href="/">Voltar</a>
      </div>
      <form action="/pmsp/resumo" method="get" class="summary-form">
        <label>Ano
          <input type="number" name="ano" value="{ano}" min="2005" max="2100">
        </label>
        <button type="submit">Atualizar</button>
      </form>
      <div class="metrics">
        <div><span>Total</span><strong>{total}</strong></div>
        <div><span>Sem fornecedor</span><strong>{missing_fornecedor}</strong></div>
        <div><span>Órgão suspeito</span><strong>{suspicious_orgao}</strong></div>
      </div>
      <div class="grid">
        {render_top_list("Top 10 órgãos", top_orgaos)}
        {render_top_list("Top 10 modalidades", top_modalidades)}
        {render_top_list("Top 10 fornecedores", top_fornecedores)}
      </div>
    </section>
    """
    return html_page("Resumo PMSP", body)


def top_counts(session: Session, field: Any, ano: int) -> list[tuple[str, int]]:
    total = func.count().label("total")
    rows = session.execute(
        select(field, total)
        .where(PmspLicitacao.ano == ano, field.is_not(None), field != "")
        .group_by(field)
        .order_by(total.desc())
        .limit(10)
    )
    return [(str(value), int(count)) for value, count in rows]


def build_criteria(*, ano: int, orgao: str | None, termo: str | None, limite: int) -> str:
    parts = [f"ano={ano}", f"limite={limite}"]
    if orgao:
        parts.append(f"órgão contém '{orgao.strip()}'")
    if termo:
        parts.append(f"objeto contém '{termo.strip()}'")
    return "; ".join(parts)


def render_pmsp_table(rows: list[PmspLicitacao]) -> str:
    if not rows:
        return '<p class="empty">Nenhum registro encontrado.</p>'
    body = "\n".join(
        f"""
        <tr>
          <td>{safe(record.orgao)}</td>
          <td>{safe(record.modalidade)}</td>
          <td>{safe(record.numero_processo)}</td>
          <td>{safe(record.numero_contrato)}</td>
          <td>{safe(record.fornecedor)}</td>
          <td class="object-cell">{safe(record.objeto)}</td>
        </tr>
        """
        for record in rows
    )
    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Órgão</th>
            <th>Modalidade</th>
            <th>Processo</th>
            <th>Contrato</th>
            <th>Fornecedor</th>
            <th>Objeto</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    """


def render_top_list(title: str, rows: list[tuple[str, int]]) -> str:
    if not rows:
        items = '<li class="muted">Sem registros.</li>'
    else:
        items = "\n".join(f"<li><span>{safe(label)}</span><strong>{count}</strong></li>" for label, count in rows)
    return f"""
    <section class="mini-panel">
      <h2>{escape(title)}</h2>
      <ol>{items}</ol>
    </section>
    """


def render_error_panel(message: str, exc: Exception) -> str:
    return f"""
    <section class="panel">
      <h1>HERMES — Rastreamento de Publicações</h1>
      <p class="error">{escape(message)}</p>
      <p class="muted">Erro: {escape(exc.__class__.__name__)}</p>
      <a class="button secondary" href="/">Voltar</a>
    </section>
    """


def html_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2933;
      --muted: #5b6673;
      --line: #d9dee5;
      --primary: #1f6feb;
      --primary-dark: #1557bd;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}
    main {{
      width: min(1180px, calc(100vw - 32px));
      margin: 32px auto;
    }}
    h1 {{ margin: 0 0 18px; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .hero {{
      margin-bottom: 18px;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 1px 2px rgba(20, 28, 38, 0.06);
    }}
    .hero h1 {{
      font-size: 44px;
      margin-bottom: 8px;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--primary);
      font-weight: 700;
      text-transform: uppercase;
      font-size: 13px;
    }}
    .lead {{
      max-width: 780px;
      color: var(--muted);
      font-size: 18px;
      margin: 0 0 18px;
    }}
    .mission-form {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: end;
      margin: 18px 0 12px;
    }}
    .mission-form label {{
      color: var(--text);
      font-size: 16px;
    }}
    .mission-form button {{
      min-width: 140px;
      min-height: 48px;
    }}
    .mission-quote {{
      padding: 14px;
      border-left: 4px solid var(--primary);
      background: #f0f5ff;
      font-size: 18px;
    }}
    .quick-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .module-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(240px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .module-card {{
      display: grid;
      gap: 8px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--text);
      background: var(--panel);
      text-decoration: none;
      box-shadow: 0 1px 2px rgba(20, 28, 38, 0.06);
    }}
    .module-card:hover {{
      border-color: var(--primary);
    }}
    .module-card strong {{
      font-size: 18px;
    }}
    .module-card span {{
      color: var(--muted);
    }}
    .panel, .mini-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 1px 2px rgba(20, 28, 38, 0.06);
    }}
    .search-form, .summary-form {{
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 14px;
      align-items: end;
    }}
    .summary-form {{
      grid-template-columns: minmax(140px, 220px) auto;
      justify-content: start;
      margin-bottom: 18px;
    }}
    label {{ display: grid; gap: 6px; font-weight: 700; color: var(--muted); }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      color: var(--text);
      background: #fff;
    }}
    textarea {{ resize: vertical; min-height: 110px; }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
      color: #fff;
      background: var(--primary);
    }}
    button:hover, .button:hover {{ background: var(--primary-dark); }}
    .secondary {{ color: var(--text); background: #eef2f7; }}
    .secondary:hover {{ background: #e3e9f2; }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .example-list {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 7px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--text);
      background: #fff;
      text-decoration: none;
      font-size: 14px;
    }}
    .pill:hover {{ border-color: var(--primary); }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    .muted {{ color: var(--muted); }}
    .error {{ color: var(--danger); font-weight: 700; }}
    .empty {{ padding: 18px; border: 1px dashed var(--line); border-radius: 8px; color: var(--muted); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #f0f3f7; font-size: 13px; color: var(--muted); }}
    td {{ font-size: 14px; }}
    .object-cell {{ min-width: 360px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: 12px; margin: 18px 0; }}
    .metrics div {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fbfcfe; }}
    .metrics span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metrics strong {{ display: block; margin-top: 4px; font-size: 26px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: 14px; }}
    ol {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 8px 0; }}
    li strong {{ float: right; margin-left: 12px; }}
    @media (max-width: 820px) {{
      .search-form, .summary-form, .metrics, .grid, .module-grid, .mission-form {{ grid-template-columns: 1fr; }}
      .hero h1 {{ font-size: 34px; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      main {{ width: min(100vw - 20px, 1180px); margin: 16px auto; }}
    }}
  </style>
</head>
<body>
  <main>{body}</main>
</body>
</html>"""
    )


def safe(value: Any) -> str:
    if value is None or value == "":
        return '<span class="muted">-</span>'
    return escape(str(value))
