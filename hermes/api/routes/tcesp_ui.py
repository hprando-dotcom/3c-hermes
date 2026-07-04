from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import escape
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.api.routes.pmsp_ui import html_page, render_error_panel, render_top_list, safe
from hermes.connectors.tcesp.normalizer import slugify
from hermes.database.models import TceSpDespesa, TceSpMunicipio, TceSpReceita
from hermes.database.session import get_session

router = APIRouter(tags=["tcesp"])


@router.get("/tcesp", response_class=HTMLResponse, include_in_schema=False)
def tcesp_home() -> HTMLResponse:
    body = """
    <section class="panel">
      <div class="topbar">
        <h1>TCE-SP</h1>
        <a class="button secondary" href="/">HERMES</a>
      </div>
      <p class="muted">Consulta das bases de transparência municipal do Tribunal de Contas do Estado de São Paulo.</p>
      <div class="actions">
        <a class="button" href="/tcesp/municipios">Carregar municípios</a>
        <a class="button secondary" href="/tcesp/resumo?ano=2015">Resumo TCE-SP</a>
      </div>
      <div class="module-grid">
        <a class="module-card" href="/tcesp/municipios"><strong>Municípios</strong><span>Lista local dos municípios disponíveis.</span></a>
        <a class="module-card" href="/tcesp/despesas?municipio=balsamo&ano=2015&mes=1"><strong>Despesas</strong><span>Consulta por município, ano, mês, órgão e fornecedor.</span></a>
        <a class="module-card" href="/tcesp/receitas?municipio=balsamo&ano=2015&mes=1"><strong>Receitas</strong><span>Consulta por município, ano, mês e termo.</span></a>
        <a class="module-card" href="/api/tcesp/resumo?ano=2015"><strong>JSON</strong><span>Endpoints simples para futura interface dedicada.</span></a>
      </div>
      <section class="mini-panel">
        <h2>Consulta</h2>
        <form action="/tcesp/buscar" method="get" class="search-form">
          <label>Município <input name="municipio" value="balsamo"></label>
          <label>Ano <input type="number" name="ano" value="2015"></label>
          <label>Mês <input type="number" name="mes" value="1" min="1" max="12"></label>
          <label>Tipo
            <select name="tipo">
              <option value="despesas">Despesas</option>
              <option value="receitas">Receitas</option>
            </select>
          </label>
          <label>Termo <input name="termo" placeholder="Opcional"></label>
          <label>Limite <input type="number" name="limite" value="50" min="1" max="500"></label>
          <button type="submit">Buscar</button>
        </form>
      </section>
    </section>
    """
    return html_page("TCE-SP", body)


@router.get("/tcesp/buscar", response_class=RedirectResponse, include_in_schema=False)
def tcesp_search_redirect(
    tipo: str = Query(default="despesas"),
    municipio: str = Query(default="balsamo"),
    ano: int = Query(default=2015),
    mes: int = Query(default=1, ge=1, le=12),
    termo: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=500),
) -> RedirectResponse:
    target = "/tcesp/receitas" if tipo == "receitas" else "/tcesp/despesas"
    query = {"municipio": municipio, "ano": ano, "mes": mes, "limite": limite}
    if termo:
        query["termo"] = termo
    return RedirectResponse(f"{target}?{urlencode(query)}", status_code=303)


@router.get("/tcesp/municipios", response_class=HTMLResponse, include_in_schema=False)
def tcesp_municipios_page(
    q: str | None = Query(default=None),
    limite: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        rows = query_municipios(session, q=q, limite=limite)
        total = count_municipios(session, q=q)
    except SQLAlchemyError as exc:
        return html_page("Municípios TCE-SP", render_error_panel("Não foi possível consultar `tcesp_municipios`.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Municípios TCE-SP</h1>
        <a class="button secondary" href="/tcesp">Voltar</a>
      </div>
      <form action="/tcesp/municipios" method="get" class="summary-form">
        <label>Busca <input name="q" value="{escape(q or '')}" placeholder="Ex.: bálsamo"></label>
        <label>Limite <input type="number" name="limite" value="{limite}" min="1" max="1000"></label>
        <button type="submit">Buscar</button>
      </form>
      <p><strong>Total encontrado:</strong> {total}</p>
      {render_municipios_table(rows)}
    </section>
    """
    return html_page("Municípios TCE-SP", body)


@router.get("/tcesp/despesas", response_class=HTMLResponse, include_in_schema=False)
def tcesp_despesas_page(
    municipio: str = Query(default="balsamo"),
    ano: int = Query(default=2015),
    mes: int | None = Query(default=None, ge=1, le=12),
    termo: str | None = Query(default=None),
    fornecedor: str | None = Query(default=None),
    orgao: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        rows = query_despesas(
            session,
            municipio=municipio,
            ano=ano,
            mes=mes,
            termo=termo,
            fornecedor=fornecedor,
            orgao=orgao,
            limite=limite,
        )
        total = count_despesas(session, municipio=municipio, ano=ano, mes=mes, termo=termo, fornecedor=fornecedor, orgao=orgao)
    except SQLAlchemyError as exc:
        return html_page("Despesas TCE-SP", render_error_panel("Não foi possível consultar `tcesp_despesas`.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Despesas TCE-SP</h1>
        <a class="button secondary" href="/tcesp">Voltar</a>
      </div>
      {render_tcesp_filters("/tcesp/despesas", municipio, ano, mes, termo, limite, fornecedor=fornecedor, orgao=orgao)}
      <p class="muted">Critérios: município={escape(municipio)}, ano={ano}, mês={mes or 'todos'}, órgão={escape(orgao or 'todos')}, limite={limite}</p>
      <p><strong>Total encontrado:</strong> {total}</p>
      {render_despesas_table(rows)}
    </section>
    """
    return html_page("Despesas TCE-SP", body)


@router.get("/tcesp/receitas", response_class=HTMLResponse, include_in_schema=False)
def tcesp_receitas_page(
    municipio: str = Query(default="balsamo"),
    ano: int = Query(default=2015),
    mes: int | None = Query(default=None, ge=1, le=12),
    termo: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        rows = query_receitas(session, municipio=municipio, ano=ano, mes=mes, termo=termo, limite=limite)
        total = count_receitas(session, municipio=municipio, ano=ano, mes=mes, termo=termo)
    except SQLAlchemyError as exc:
        return html_page("Receitas TCE-SP", render_error_panel("Não foi possível consultar `tcesp_receitas`.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Receitas TCE-SP</h1>
        <a class="button secondary" href="/tcesp">Voltar</a>
      </div>
      {render_tcesp_filters("/tcesp/receitas", municipio, ano, mes, termo, limite)}
      <p class="muted">Critérios: município={escape(municipio)}, ano={ano}, mês={mes or 'todos'}, limite={limite}</p>
      <p><strong>Total encontrado:</strong> {total}</p>
      {render_receitas_table(rows)}
    </section>
    """
    return html_page("Receitas TCE-SP", body)


@router.get("/tcesp/resumo", response_class=HTMLResponse, include_in_schema=False)
def tcesp_resumo_page(
    ano: int = Query(default=2015),
    municipio: str | None = Query(default=None),
    mes: int | None = Query(default=None, ge=1, le=12),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    try:
        summary = build_tcesp_summary(session, ano=ano, municipio=municipio, mes=mes)
    except SQLAlchemyError as exc:
        return html_page("Resumo TCE-SP", render_error_panel("Não foi possível gerar o resumo TCE-SP.", exc))

    body = f"""
    <section class="panel">
      <div class="topbar">
        <h1>Resumo TCE-SP</h1>
        <a class="button secondary" href="/tcesp">Voltar</a>
      </div>
      <form action="/tcesp/resumo" method="get" class="summary-form">
        <label>Ano <input type="number" name="ano" value="{ano}"></label>
        <label>Mês <input type="number" name="mes" value="{mes or ''}" min="1" max="12" placeholder="Todos"></label>
        <label>Município <input name="municipio" value="{escape(municipio or '')}" placeholder="Opcional"></label>
        <button type="submit">Atualizar</button>
      </form>
      <div class="metrics">
        <div><span>Municípios</span><strong>{summary['municipios_total']}</strong></div>
        <div><span>Despesas</span><strong>{summary['despesas_total']}</strong></div>
        <div><span>Receitas</span><strong>{summary['receitas_total']}</strong></div>
      </div>
      <div class="grid">
        {render_top_list("Top fornecedores por valor", summary["top_fornecedores_por_valor"])}
        {render_top_list("Top órgãos por despesa", summary["top_orgaos_por_despesa"])}
        {render_top_list("Top fontes de receita", summary["top_fontes_receita"])}
      </div>
      {render_quality_alerts(summary["quality_alerts"])}
    </section>
    """
    return html_page("Resumo TCE-SP", body)


@router.get("/api/tcesp/municipios")
def api_tcesp_municipios(
    q: str | None = None,
    limite: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        rows = query_municipios(session, q=q, limite=limite)
        return {"ok": True, "total": count_municipios(session, q=q), "items": [serialize_municipio(row) for row in rows]}
    except SQLAlchemyError as exc:
        return json_error(exc, "tcesp_municipios")


@router.get("/api/tcesp/despesas")
def api_tcesp_despesas(
    municipio: str = "balsamo",
    ano: int = 2015,
    mes: int | None = Query(default=None, ge=1, le=12),
    termo: str | None = None,
    fornecedor: str | None = None,
    orgao: str | None = None,
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        rows = query_despesas(
            session,
            municipio=municipio,
            ano=ano,
            mes=mes,
            termo=termo,
            fornecedor=fornecedor,
            orgao=orgao,
            limite=limite,
        )
        total = count_despesas(session, municipio=municipio, ano=ano, mes=mes, termo=termo, fornecedor=fornecedor, orgao=orgao)
        return {"ok": True, "total": total, "items": [serialize_despesa(row) for row in rows]}
    except SQLAlchemyError as exc:
        return json_error(exc, "tcesp_despesas")


@router.get("/api/tcesp/receitas")
def api_tcesp_receitas(
    municipio: str = "balsamo",
    ano: int = 2015,
    mes: int | None = Query(default=None, ge=1, le=12),
    termo: str | None = None,
    limite: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        rows = query_receitas(session, municipio=municipio, ano=ano, mes=mes, termo=termo, limite=limite)
        total = count_receitas(session, municipio=municipio, ano=ano, mes=mes, termo=termo)
        return {"ok": True, "total": total, "items": [serialize_receita(row) for row in rows]}
    except SQLAlchemyError as exc:
        return json_error(exc, "tcesp_receitas")


@router.get("/api/tcesp/resumo")
def api_tcesp_resumo(
    ano: int = 2015,
    municipio: str | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return {"ok": True, **build_tcesp_summary(session, ano=ano, municipio=municipio, mes=mes)}
    except SQLAlchemyError as exc:
        return json_error(exc, "tcesp_resumo")


def query_municipios(session: Session, *, q: str | None, limite: int) -> list[TceSpMunicipio]:
    statement = select(TceSpMunicipio)
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(
            TceSpMunicipio.municipio_slug.ilike(term) | TceSpMunicipio.municipio_extenso.ilike(term)
        )
    statement = statement.order_by(TceSpMunicipio.municipio_extenso).limit(limite)
    return list(session.scalars(statement))


def count_municipios(session: Session, *, q: str | None = None) -> int:
    statement = select(func.count()).select_from(TceSpMunicipio)
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(
            TceSpMunicipio.municipio_slug.ilike(term) | TceSpMunicipio.municipio_extenso.ilike(term)
        )
    return int(session.scalar(statement) or 0)


def query_despesas(
    session: Session,
    *,
    municipio: str,
    ano: int,
    mes: int | None,
    termo: str | None,
    fornecedor: str | None,
    orgao: str | None,
    limite: int,
) -> list[TceSpDespesa]:
    statement = select(TceSpDespesa).where(*despesa_conditions(municipio, ano, mes, termo, fornecedor, orgao))
    statement = statement.order_by(TceSpDespesa.dt_emissao_despesa.desc().nullslast(), TceSpDespesa.id.desc()).limit(limite)
    return list(session.scalars(statement))


def count_despesas(
    session: Session,
    *,
    municipio: str | None = None,
    ano: int | None,
    mes: int | None = None,
    termo: str | None = None,
    fornecedor: str | None = None,
    orgao: str | None = None,
) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(TceSpDespesa).where(*despesa_conditions(municipio, ano, mes, termo, fornecedor, orgao))
        )
        or 0
    )


def despesa_conditions(
    municipio: str | None,
    ano: int | None,
    mes: int | None,
    termo: str | None,
    fornecedor: str | None,
    orgao: str | None,
) -> list[Any]:
    conditions: list[Any] = []
    if ano:
        conditions.append(TceSpDespesa.exercicio == ano)
    if municipio:
        conditions.append(TceSpDespesa.municipio_slug == slugify(municipio))
    if mes:
        conditions.append(TceSpDespesa.mes_numero == mes)
    if termo:
        conditions.append(TceSpDespesa.evento.ilike(f"%{termo.strip()}%") | TceSpDespesa.orgao.ilike(f"%{termo.strip()}%"))
    if fornecedor:
        conditions.append(TceSpDespesa.nm_fornecedor.ilike(f"%{fornecedor.strip()}%"))
    if orgao:
        conditions.append(TceSpDespesa.orgao.ilike(f"%{orgao.strip()}%"))
    return conditions


def query_receitas(
    session: Session,
    *,
    municipio: str,
    ano: int,
    mes: int | None,
    termo: str | None,
    limite: int,
) -> list[TceSpReceita]:
    statement = select(TceSpReceita).where(*receita_conditions(municipio, ano, mes, termo))
    statement = statement.order_by(TceSpReceita.id.desc()).limit(limite)
    return list(session.scalars(statement))


def count_receitas(
    session: Session,
    *,
    municipio: str | None = None,
    ano: int | None,
    mes: int | None = None,
    termo: str | None = None,
) -> int:
    return int(session.scalar(select(func.count()).select_from(TceSpReceita).where(*receita_conditions(municipio, ano, mes, termo))) or 0)


def receita_conditions(municipio: str | None, ano: int | None, mes: int | None, termo: str | None) -> list[Any]:
    conditions: list[Any] = []
    if ano:
        conditions.append(TceSpReceita.exercicio == ano)
    if municipio:
        conditions.append(TceSpReceita.municipio_slug == slugify(municipio))
    if mes:
        conditions.append(TceSpReceita.mes_numero == mes)
    if termo:
        term = f"%{termo.strip()}%"
        conditions.append(
            TceSpReceita.ds_fonte_recurso.ilike(term)
            | TceSpReceita.ds_alinea.ilike(term)
            | TceSpReceita.ds_subalinea.ilike(term)
        )
    return conditions


def build_tcesp_summary(session: Session, *, ano: int | None, municipio: str | None, mes: int | None) -> dict[str, Any]:
    despesa_filter = despesa_conditions(municipio, ano, mes, None, None, None)
    receita_filter = receita_conditions(municipio, ano, mes, None)
    sem_fornecedor = int(
        session.scalar(
            select(func.count())
            .select_from(TceSpDespesa)
            .where(*despesa_filter, (TceSpDespesa.nm_fornecedor.is_(None) | (TceSpDespesa.nm_fornecedor == "")))
        )
        or 0
    )
    despesas_sem_valor = int(
        session.scalar(select(func.count()).select_from(TceSpDespesa).where(*despesa_filter, TceSpDespesa.vl_despesa.is_(None))) or 0
    )
    receitas_sem_valor = int(
        session.scalar(select(func.count()).select_from(TceSpReceita).where(*receita_filter, TceSpReceita.vl_arrecadacao.is_(None))) or 0
    )
    return {
        "ano": ano,
        "municipio": municipio,
        "mes": mes,
        "municipios_total": int(session.scalar(select(func.count()).select_from(TceSpMunicipio)) or 0),
        "despesas_total": int(session.scalar(select(func.count()).select_from(TceSpDespesa).where(*despesa_filter)) or 0),
        "receitas_total": int(session.scalar(select(func.count()).select_from(TceSpReceita).where(*receita_filter)) or 0),
        "top_fornecedores_por_valor": top_sums(session, TceSpDespesa.nm_fornecedor, TceSpDespesa.vl_despesa, TceSpDespesa, despesa_filter),
        "top_orgaos_por_despesa": top_sums(session, TceSpDespesa.orgao, TceSpDespesa.vl_despesa, TceSpDespesa, despesa_filter),
        "top_fontes_receita": top_sums(session, TceSpReceita.ds_fonte_recurso, TceSpReceita.vl_arrecadacao, TceSpReceita, receita_filter),
        "quality_alerts": [
            f"Despesas sem fornecedor: {sem_fornecedor}",
            f"Despesas sem valor: {despesas_sem_valor}",
            f"Receitas sem valor: {receitas_sem_valor}",
        ],
    }


def top_counts(session: Session, field: Any, model: Any, conditions: list[Any]) -> list[tuple[str, int]]:
    total = func.count().label("total")
    rows = session.execute(
        select(field, total)
        .select_from(model)
        .where(*conditions, field.is_not(None), field != "")
        .group_by(field)
        .order_by(total.desc())
        .limit(10)
    )
    return [(str(value), int(count)) for value, count in rows]


def top_sums(session: Session, field: Any, amount_field: Any, model: Any, conditions: list[Any]) -> list[tuple[str, str]]:
    total = func.coalesce(func.sum(amount_field), 0).label("total")
    rows = session.execute(
        select(field, total)
        .select_from(model)
        .where(*conditions, field.is_not(None), field != "", amount_field.is_not(None))
        .group_by(field)
        .order_by(total.desc())
        .limit(10)
    )
    return [(str(value), str(total_value)) for value, total_value in rows]


def render_tcesp_filters(
    action: str,
    municipio: str,
    ano: int,
    mes: int | None,
    termo: str | None,
    limite: int,
    *,
    fornecedor: str | None = None,
    orgao: str | None = None,
) -> str:
    fornecedor_field = ""
    if fornecedor is not None or action.endswith("despesas"):
        fornecedor_field = f'<label>Fornecedor <input name="fornecedor" value="{escape(fornecedor or "")}" placeholder="Opcional"></label>'
    orgao_field = ""
    if action.endswith("despesas"):
        orgao_field = f'<label>Órgão <input name="orgao" value="{escape(orgao or "")}" placeholder="Opcional"></label>'
    return f"""
    <form action="{escape(action)}" method="get" class="search-form">
      <label>Município <input name="municipio" value="{escape(municipio)}"></label>
      <label>Ano <input type="number" name="ano" value="{ano}"></label>
      <label>Mês <input type="number" name="mes" value="{mes or ''}" min="1" max="12" placeholder="Todos"></label>
      <label>Termo <input name="termo" value="{escape(termo or '')}" placeholder="Opcional"></label>
      {orgao_field}
      {fornecedor_field}
      <label>Limite <input type="number" name="limite" value="{limite}" min="1" max="500"></label>
      <button type="submit">Buscar</button>
    </form>
    """


def render_municipios_table(rows: list[TceSpMunicipio]) -> str:
    if not rows:
        return '<p class="empty">Nenhum município encontrado. Rode a ingestão de municípios do TCE-SP antes da consulta.</p>'
    body = "\n".join(
        f"<tr><td>{safe(row.municipio_extenso)}</td><td>{safe(row.municipio_slug)}</td></tr>"
        for row in rows
    )
    return f"<div class=\"table-wrap\"><table><thead><tr><th>Município</th><th>Slug</th></tr></thead><tbody>{body}</tbody></table></div>"


def render_quality_alerts(alerts: list[str]) -> str:
    items = "\n".join(f"<li>{safe(alert)}</li>" for alert in alerts)
    return f"""
    <section class="mini-panel">
      <h2>Alertas de qualidade</h2>
      <ul>{items}</ul>
    </section>
    """


def render_despesas_table(rows: list[TceSpDespesa]) -> str:
    if not rows:
        return '<p class="empty">Nenhuma despesa encontrada.</p>'
    body = "\n".join(
        f"""
        <tr>
          <td>{safe(row.municipio_extenso or row.municipio_slug)}</td>
          <td>{safe(f"{row.exercicio}/{row.mes_numero}")}</td>
          <td>{safe(row.orgao)}</td>
          <td>{safe(row.evento)}</td>
          <td>{safe(row.nr_empenho)}</td>
          <td>{safe(row.nm_fornecedor)}</td>
          <td>{safe(row.vl_despesa)}</td>
          <td>{safe(row.dt_emissao_despesa)}</td>
        </tr>
        """
        for row in rows
    )
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr><th>Município</th><th>Ano/mês</th><th>Órgão</th><th>Evento</th><th>Empenho</th><th>Fornecedor</th><th>Valor</th><th>Emissão</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    """


def render_receitas_table(rows: list[TceSpReceita]) -> str:
    if not rows:
        return '<p class="empty">Nenhuma receita encontrada.</p>'
    body = "\n".join(
        f"""
        <tr>
          <td>{safe(row.municipio_extenso or row.municipio_slug)}</td>
          <td>{safe(f"{row.exercicio}/{row.mes_numero}")}</td>
          <td>{safe(row.orgao)}</td>
          <td>{safe(row.ds_fonte_recurso)}</td>
          <td>{safe(row.ds_cd_aplicacao_fixo)}</td>
          <td>{safe(row.ds_alinea)}</td>
          <td class="object-cell">{safe(row.ds_subalinea)}</td>
          <td>{safe(row.vl_arrecadacao)}</td>
        </tr>
        """
        for row in rows
    )
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr><th>Município</th><th>Ano/mês</th><th>Órgão</th><th>Fonte</th><th>Aplicação</th><th>Alínea</th><th>Subalínea</th><th>Valor</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    """


def serialize_municipio(row: TceSpMunicipio) -> dict[str, Any]:
    return {"municipio_slug": row.municipio_slug, "municipio_extenso": row.municipio_extenso}


def serialize_despesa(row: TceSpDespesa) -> dict[str, Any]:
    return serialize_fields(
        row,
        [
            "id",
            "municipio_slug",
            "municipio_extenso",
            "exercicio",
            "mes_numero",
            "mes_nome",
            "orgao",
            "evento",
            "nr_empenho",
            "id_fornecedor",
            "nm_fornecedor",
            "dt_emissao_despesa",
            "vl_despesa",
        ],
    )


def serialize_receita(row: TceSpReceita) -> dict[str, Any]:
    return serialize_fields(
        row,
        [
            "id",
            "municipio_slug",
            "municipio_extenso",
            "exercicio",
            "mes_numero",
            "mes_nome",
            "orgao",
            "ds_fonte_recurso",
            "ds_cd_aplicacao_fixo",
            "ds_alinea",
            "ds_subalinea",
            "vl_arrecadacao",
        ],
    )


def serialize_fields(row: Any, fields: list[str]) -> dict[str, Any]:
    return {field: json_value(getattr(row, field)) for field in fields}


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def json_error(exc: Exception, source: str) -> dict[str, Any]:
    return {"ok": False, "source": source, "error": exc.__class__.__name__, "items": [], "total": 0}
