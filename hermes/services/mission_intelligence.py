from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from hermes.database.models import PmspLicitacao, TceSpDespesa, TceSpReceita

DEFAULT_YEAR = 2015
DEFAULT_LIMIT = 12

WORK_TERMS = ["obra", "obras", "engenharia", "manutencao", "reforma", "acessibilidade", "calcada", "pavimento"]
HEALTH_TERMS = ["saude", "hospital", "ubs", "ambulatorio"]
EDUCATION_TERMS = ["educacao", "escola", "creche", "ensino"]
SUPPLIER_TERMS = ["fornecedor", "fornecedores", "empresa", "empresas"]
ORG_TERMS = ["orgaos mais ativos", "orgaos ativos", "orgao", "orgaos", "secretarias"]
TCE_TERMS = ["tce", "balsamo", "municipio", "municipal", "despesa", "receita"]
SEARCH_VARIANTS = {
    "manutencao": ["manutencao", "manutenção"],
    "calcada": ["calcada", "calçada"],
    "saude": ["saude", "saúde"],
    "educacao": ["educacao", "educação"],
}


@dataclass(slots=True)
class MissionAnalysis:
    mission: str
    normalized: str
    understood: bool
    themes: list[str] = field(default_factory=list)
    pmsP_terms: list[str] = field(default_factory=list)
    include_pmsP: bool = False
    include_tcesp: bool = False
    wants_suppliers: bool = False
    wants_orgs: bool = False
    municipio_slug: str | None = None
    suggestions: list[str] = field(default_factory=list)


def investigate_mission(session: Session, mission: str, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    analysis = analyze_mission(mission)
    result: dict[str, Any] = {
        "mission": mission,
        "analysis": analysis,
        "bases": [],
        "summary": "",
        "findings": [],
        "rankings": {},
        "records": [],
        "quality_alerts": [],
        "next_questions": next_questions(analysis),
        "errors": [],
    }

    if not analysis.understood:
        result["summary"] = (
            "Ainda nao entendi a missao com seguranca. Posso investigar obras, manutencao, saude, educacao, "
            "fornecedores, orgaos ativos ou dados municipais do TCE-SP."
        )
        result["findings"] = ["Escolha uma das missoes sugeridas ou descreva o tema com mais contexto."]
        return result

    if analysis.include_pmsP:
        try:
            add_pmsp_findings(session, analysis, result, limit=limit)
        except SQLAlchemyError as exc:
            result["errors"].append(f"PMSP indisponivel: {exc.__class__.__name__}")

    if analysis.include_tcesp:
        try:
            add_tcesp_findings(session, analysis, result, limit=limit)
        except SQLAlchemyError as exc:
            result["errors"].append(f"TCE-SP indisponivel: {exc.__class__.__name__}")

    if not result["bases"]:
        result["summary"] = "A missao foi interpretada, mas nenhuma base disponivel respondeu com dados consultaveis agora."
    else:
        result["summary"] = build_executive_summary(analysis, result)
    if not result["findings"] and result["errors"]:
        result["findings"].append("A investigacao encontrou erro ao consultar as bases persistidas. Verifique o status do sistema.")
    return result


def analyze_mission(mission: str) -> MissionAnalysis:
    normalized = normalize_text(mission)
    pmsP_terms: list[str] = []
    themes: list[str] = []

    if any(term in normalized for term in WORK_TERMS):
        pmsP_terms.extend(WORK_TERMS)
        themes.append("obras e manutencao")
    if any(term in normalized for term in HEALTH_TERMS):
        pmsP_terms.extend(HEALTH_TERMS)
        themes.append("saude")
    if any(term in normalized for term in EDUCATION_TERMS):
        pmsP_terms.extend(EDUCATION_TERMS)
        themes.append("educacao")

    wants_suppliers = any(term in normalized for term in SUPPLIER_TERMS)
    wants_orgs = any(term in normalized for term in ORG_TERMS)
    include_tcesp = any(term in normalized for term in TCE_TERMS)
    municipio_slug = detect_municipio(normalized)

    include_pmsP = bool(pmsP_terms or wants_suppliers or wants_orgs or "sao paulo" in normalized)
    if wants_suppliers:
        themes.append("fornecedores")
    if wants_orgs:
        themes.append("orgaos ativos")
    if include_tcesp:
        themes.append("TCE-SP")

    understood = include_pmsP or include_tcesp
    return MissionAnalysis(
        mission=mission,
        normalized=normalized,
        understood=understood,
        themes=dedupe(themes),
        pmsP_terms=dedupe(pmsP_terms),
        include_pmsP=include_pmsP,
        include_tcesp=include_tcesp,
        wants_suppliers=wants_suppliers,
        wants_orgs=wants_orgs,
        municipio_slug=municipio_slug,
        suggestions=default_suggestions(),
    )


def add_pmsp_findings(session: Session, analysis: MissionAnalysis, result: dict[str, Any], *, limit: int) -> None:
    conditions: list[Any] = [PmspLicitacao.ano == DEFAULT_YEAR]
    term_condition = pmsp_term_condition(analysis.pmsP_terms)
    if term_condition is not None:
        conditions.append(term_condition)

    total = int(session.scalar(select(func.count()).select_from(PmspLicitacao).where(*conditions)) or 0)
    missing_supplier = int(
        session.scalar(
            select(func.count())
            .select_from(PmspLicitacao)
            .where(*conditions, or_(PmspLicitacao.fornecedor.is_(None), PmspLicitacao.fornecedor == ""))
        )
        or 0
    )
    missing_contract = int(
        session.scalar(
            select(func.count())
            .select_from(PmspLicitacao)
            .where(*conditions, or_(PmspLicitacao.numero_contrato.is_(None), PmspLicitacao.numero_contrato == ""))
        )
        or 0
    )
    records = list(
        session.scalars(
            select(PmspLicitacao)
            .where(*conditions)
            .order_by(PmspLicitacao.data_publicacao.desc().nullslast(), PmspLicitacao.id.desc())
            .limit(limit)
        )
    )

    result["bases"].append(f"PMSP Licitacoes {DEFAULT_YEAR}")
    result["findings"].append(f"PMSP retornou {total} registros aderentes a missao.")
    if analysis.pmsP_terms:
        result["findings"].append(f"Termos investigados no objeto/orgao: {', '.join(analysis.pmsP_terms[:8])}.")
    result["rankings"]["orgaos PMSP"] = top_counts(session, PmspLicitacao.orgao, PmspLicitacao, conditions)
    result["rankings"]["fornecedores PMSP"] = top_counts(session, PmspLicitacao.fornecedor, PmspLicitacao, conditions)
    result["records"].extend(pmsp_record_to_dict(record) for record in records)
    result["quality_alerts"].append(f"PMSP registros sem fornecedor no recorte: {missing_supplier}")
    result["quality_alerts"].append(f"PMSP registros sem contrato no recorte: {missing_contract}")


def add_tcesp_findings(session: Session, analysis: MissionAnalysis, result: dict[str, Any], *, limit: int) -> None:
    despesa_conditions: list[Any] = [TceSpDespesa.exercicio == DEFAULT_YEAR]
    receita_conditions: list[Any] = [TceSpReceita.exercicio == DEFAULT_YEAR]
    if analysis.municipio_slug:
        despesa_conditions.append(TceSpDespesa.municipio_slug == analysis.municipio_slug)
        receita_conditions.append(TceSpReceita.municipio_slug == analysis.municipio_slug)

    despesas_total = int(session.scalar(select(func.count()).select_from(TceSpDespesa).where(*despesa_conditions)) or 0)
    receitas_total = int(session.scalar(select(func.count()).select_from(TceSpReceita).where(*receita_conditions)) or 0)
    despesas = list(
        session.scalars(
            select(TceSpDespesa)
            .where(*despesa_conditions)
            .order_by(TceSpDespesa.dt_emissao_despesa.desc().nullslast(), TceSpDespesa.id.desc())
            .limit(limit)
        )
    )

    result["bases"].append(f"TCE-SP Transparencia Municipal {DEFAULT_YEAR}")
    result["findings"].append(f"TCE-SP retornou {despesas_total} despesas e {receitas_total} receitas no recorte persistido.")
    result["rankings"]["fornecedores TCE-SP"] = top_sums(
        session, TceSpDespesa.nm_fornecedor, TceSpDespesa.vl_despesa, TceSpDespesa, despesa_conditions
    )
    result["rankings"]["fontes de receita TCE-SP"] = top_sums(
        session, TceSpReceita.ds_fonte_recurso, TceSpReceita.vl_arrecadacao, TceSpReceita, receita_conditions
    )
    result["records"].extend(tcesp_despesa_to_dict(record) for record in despesas)
    result["quality_alerts"].append(f"TCE-SP despesas sem fornecedor no recorte: {count_null(session, TceSpDespesa, TceSpDespesa.nm_fornecedor, despesa_conditions)}")


def pmsp_term_condition(terms: list[str]) -> Any | None:
    if not terms:
        return None
    clauses = []
    for term in terms:
        for variant in SEARCH_VARIANTS.get(term, [term]):
            like = f"%{variant}%"
            clauses.append(PmspLicitacao.objeto.ilike(like))
            clauses.append(PmspLicitacao.orgao.ilike(like))
            clauses.append(PmspLicitacao.modalidade.ilike(like))
    return or_(*clauses)


def top_counts(session: Session, field: Any, model: Any, conditions: list[Any], *, limit: int = 5) -> list[tuple[str, int]]:
    total = func.count().label("total")
    rows = session.execute(
        select(field, total)
        .select_from(model)
        .where(*conditions, field.is_not(None), field != "")
        .group_by(field)
        .order_by(total.desc())
        .limit(limit)
    )
    return [(str(value), int(count)) for value, count in rows]


def top_sums(session: Session, field: Any, amount_field: Any, model: Any, conditions: list[Any], *, limit: int = 5) -> list[tuple[str, str]]:
    total = func.coalesce(func.sum(amount_field), 0).label("total")
    rows = session.execute(
        select(field, total)
        .select_from(model)
        .where(*conditions, field.is_not(None), field != "", amount_field.is_not(None))
        .group_by(field)
        .order_by(total.desc())
        .limit(limit)
    )
    return [(str(value), format_amount(total_value)) for value, total_value in rows]


def count_null(session: Session, model: Any, field: Any, conditions: list[Any]) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions, or_(field.is_(None), field == ""))) or 0)


def build_executive_summary(analysis: MissionAnalysis, result: dict[str, Any]) -> str:
    themes = ", ".join(analysis.themes) if analysis.themes else "tema solicitado"
    bases = ", ".join(result["bases"])
    first_finding = result["findings"][0] if result["findings"] else "A investigacao foi executada com os dados persistidos."
    return (
        f"Analisei {bases} para a missao sobre {themes}. {first_finding} "
        "Abaixo estao os principais achados, rankings, evidencias e alertas de qualidade."
    )


def pmsp_record_to_dict(record: PmspLicitacao) -> dict[str, Any]:
    return {
        "source": "PMSP",
        "orgao": record.orgao,
        "evento": record.evento,
        "processo": record.numero_processo,
        "contrato": record.numero_contrato,
        "fornecedor": record.fornecedor,
        "valor": format_amount(record.valor_contrato),
        "data": record.data_publicacao,
        "descricao": record.objeto,
    }


def tcesp_despesa_to_dict(record: TceSpDespesa) -> dict[str, Any]:
    return {
        "source": "TCE-SP",
        "orgao": record.orgao,
        "evento": record.evento,
        "processo": record.nr_empenho,
        "contrato": None,
        "fornecedor": record.nm_fornecedor,
        "valor": format_amount(record.vl_despesa),
        "data": record.dt_emissao_despesa,
        "descricao": f"{record.municipio_extenso or record.municipio_slug} - {record.mes_nome or record.mes_numero}/{record.exercicio}",
    }


def next_questions(analysis: MissionAnalysis) -> list[str]:
    if not analysis.understood:
        return default_suggestions()
    questions = [
        "Quais fornecedores aparecem com mais recorrencia?",
        "Quais orgaos concentram os registros?",
        "Existem registros sem fornecedor ou contrato?",
    ]
    if analysis.include_tcesp:
        questions.append("Compare despesas e receitas municipais no TCE-SP.")
    else:
        questions.append("Cruze este tema com dados municipais do TCE-SP.")
    return questions


def default_suggestions() -> list[str]:
    return [
        "Obras e manutencao em Sao Paulo",
        "Fornecedores recorrentes em contratos publicos",
        "Movimentacoes de saude",
        "Despesas municipais no TCE-SP",
        "Orgaos mais ativos",
    ]


def detect_municipio(normalized: str) -> str | None:
    if "balsamo" in normalized:
        return "balsamo"
    match = re.search(r"municipio\s+de\s+([a-z0-9-]+)", normalized)
    if match:
        return match.group(1)
    return None


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def format_amount(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)
