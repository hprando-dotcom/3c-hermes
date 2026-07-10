from __future__ import annotations

import re
import csv
import json
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from hermes.connectors.publications.html_scraper import clean_text, extract_links, extract_visible_text, is_pdf_url
from hermes.connectors.publications.hashing import stable_hash
from hermes.services.deepseek_service import DeepSeekService

FetchResult = dict[str, Any]
Fetcher = Callable[[str], FetchResult]

DEFAULT_REPORT_DIR = Path("data/reports")
DEFAULT_EXPORT_DIR = Path("data/exports")
MAX_AI_CHUNKS = 12
MAX_CHARS_PER_CHUNK = 3500
MAX_DOCUMENT_CHARS = 40000

DEFAULT_TERMS = [
    "licitação",
    "licitacao",
    "edital",
    "concorrência",
    "concorrencia",
    "pregão",
    "pregao",
    "dispensa",
    "inexigibilidade",
    "homologação",
    "homologacao",
    "adjudicação",
    "adjudicacao",
    "contrato",
    "extrato de contrato",
    "ata de registro de preços",
    "termo aditivo",
    "aditivo",
    "apostilamento",
    "rescisão",
    "prorrogação",
    "reequilíbrio",
    "reajuste",
    "obra",
    "obras",
    "engenharia",
    "manutenção",
    "manutencao",
    "reforma",
    "pavimentação",
    "pavimentacao",
    "drenagem",
    "infraestrutura",
    "contenção",
    "contencao",
    "sinalização",
    "sinalizacao",
    "projeto executivo",
    "fiscalização",
    "fiscalizacao",
    "supervisão",
    "supervisao",
]

LINK_PRIORITY_TERMS = [
    "diario",
    "diário",
    "publicacao",
    "publicação",
    "edicao",
    "edição",
    "imprensa",
    "oficial",
    "pdf",
    "licitacao",
    "licitação",
    "contrato",
    "ato",
    "extrato",
]


@dataclass(slots=True)
class GazetteLink:
    url: str
    text: str
    is_pdf: bool
    date: str | None
    date_unknown: bool
    priority_score: int


@dataclass(slots=True)
class GazetteDocument:
    url: str
    title: str
    content_type: str | None
    is_pdf: bool
    date: str | None
    text: str
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GazetteFinding:
    title: str
    date: str | None
    event_type: str
    natureza: str
    score: int
    agency: str | None
    company_name: str | None
    process_number: str | None
    contract_number: str | None
    value_text: str | None
    object_text: str | None
    summary: str
    reason: str
    matched_terms: list[str]
    snippet: str
    link: str


@dataclass(slots=True)
class InvestigationReport:
    investigation_id: str
    source_url: str
    mission_text: str
    date_start: str | None
    date_end: str | None
    strategy: str
    mission_context: dict[str, Any]
    links_found: int
    documents_analyzed: int
    findings: list[GazetteFinding]
    limitations: list[str]
    evidence_links: list[str]
    markdown: str
    markdown_path: str
    report_markdown_path: str
    report_html_path: str
    csv_path: str
    json_path: str
    zip_path: str
    used_deepseek: bool
    metrics: dict[str, Any]
    totals: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    report_html: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "source_url": self.source_url,
            "mission_text": self.mission_text,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "strategy": self.strategy,
            "deepseek_used": self.used_deepseek,
            "generated_at": self.generated_at,
            "totals": self.totals,
            "mission_context": self.mission_context,
            "links_found": self.links_found,
            "documents_analyzed": self.documents_analyzed,
            "findings": [asdict(finding) for finding in self.findings],
            "limitations": self.limitations,
            "evidence_links": self.evidence_links,
            "markdown": self.markdown,
            "markdown_path": self.markdown_path,
            "report_markdown_path": self.report_markdown_path,
            "report_html_path": self.report_html_path,
            "csv_path": self.csv_path,
            "json_path": self.json_path,
            "zip_path": self.zip_path,
            "used_deepseek": self.used_deepseek,
            "metrics": self.metrics,
        }


def run_official_gazette_investigation(
    source_url: str,
    mission_text: str,
    date_start: str | None,
    date_end: str | None,
    limit: int = 50,
    *,
    fetcher: Fetcher | None = None,
    deepseek_service: DeepSeekService | None = None,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    export_dir: Path | str | None = None,
) -> InvestigationReport:
    source_url = validate_source_url(source_url)
    limit = max(1, min(int(limit or 50), 200))
    active_fetcher = fetcher or fetch_url
    deepseek = deepseek_service or DeepSeekService()
    metrics = {"documents_analyzed": 0, "chunks_sent_to_ai": 0, "deepseek_calls": 0, "deepseek_failures": 0}
    limitations: list[str] = []

    source_response = active_fetcher(source_url)
    if source_response.get("error"):
        limitations.append(f"Falha ao acessar fonte: {source_response['error']}")
    source_text = response_text(source_response)
    source_content_type = source_response.get("content_type") or ""
    if not source_text and "pdf" not in source_content_type.lower():
        limitations.append("Fonte sem HTML/texto extraivel.")

    raw_links = extract_links(source_text, source_url) if source_text else []
    gazette_links = discover_gazette_links(raw_links, date_start=date_start, date_end=date_end, limit=limit)
    if any(link.date_unknown for link in gazette_links):
        limitations.append("Alguns links nao possuem data explicita; eles foram mantidos como data_desconhecida.")
    if not gazette_links:
        limitations.append("Nenhum link priorizado foi encontrado; a propria fonte foi analisada como documento HTML.")
        gazette_links = [
            GazetteLink(url=source_url, text="Fonte inicial", is_pdf="pdf" in source_content_type.lower(), date=None, date_unknown=True, priority_score=1)
        ]

    mission_context = build_mission_context(mission_text)
    expanded = deepseek.expand_mission_terms(mission_text)
    used_deepseek = False
    if expanded.ok and isinstance(expanded.data, dict):
        used_deepseek = True
        merge_deepseek_terms(mission_context, expanded.data)
    else:
        limitations.append(f"DeepSeek expansao indisponivel: {expanded.error}")

    documents: list[GazetteDocument] = []
    for link in gazette_links[:limit]:
        document = fetch_document(link, active_fetcher)
        documents.append(document)
        metrics["documents_analyzed"] += 1
        limitations.extend(document.limitations)

    chunks = build_relevant_chunks(documents, mission_context["all_terms"])
    unique_chunks = dedupe_chunks(chunks)[:MAX_AI_CHUNKS]
    findings: list[GazetteFinding] = []
    for chunk in unique_chunks:
        if deepseek.available:
            classification = deepseek.classify_publication_snippet(chunk["snippet"], mission_context)
            metrics["deepseek_calls"] = deepseek.calls
            metrics["deepseek_failures"] = deepseek.failures
            if classification.ok and isinstance(classification.data, dict):
                used_deepseek = True
                metrics["chunks_sent_to_ai"] += 1
                findings.append(finding_from_classification(chunk, classification.data))
                continue
            limitations.append(f"DeepSeek classificacao indisponivel para um trecho: {classification.error}")
        findings.append(deterministic_classify_chunk(chunk, mission_context["all_terms"]))

    findings = sorted([item for item in findings if item.score > 0], key=lambda item: item.score, reverse=True)
    if not findings:
        limitations.append("Nenhum trecho atingiu relevancia pelos termos e classificadores disponiveis.")

    strategy = describe_strategy(source_content_type, gazette_links, documents, used_deepseek)
    report_input = build_report_input(
        source_url=source_url,
        mission_text=mission_text,
        date_start=date_start,
        date_end=date_end,
        strategy=strategy,
        mission_context=mission_context,
        links_found=len(raw_links),
        documents=documents,
        findings=findings,
        limitations=limitations,
        used_deepseek=used_deepseek,
        metrics=metrics,
    )
    markdown = deterministic_report_markdown(report_input)
    improved = deepseek.build_investigation_report(report_input)
    metrics["deepseek_calls"] = deepseek.calls
    metrics["deepseek_failures"] = deepseek.failures
    if improved.ok and isinstance(improved.data, str) and improved.data.strip():
        used_deepseek = True
        markdown = improved.data.strip()
    elif deepseek.available:
        limitations.append(f"DeepSeek relatorio indisponivel: {improved.error}")
        markdown = deterministic_report_markdown({**report_input, "limitations": limitations})

    limitations = dedupe_strings(limitations)
    evidence_links = dedupe_strings([finding.link for finding in findings] + [doc.url for doc in documents])
    report_dir_path = Path(report_dir)
    export_dir_path = resolve_export_dir(report_dir_path, export_dir)
    investigation_id = create_investigation_id(report_dir_path, export_dir_path)
    generated_at = datetime.now().isoformat(timespec="seconds")
    totals = {
        "links_found": len(raw_links),
        "documents_analyzed": len(documents),
        "findings": len(findings),
        "limitations": len(limitations),
    }
    paths = build_dossier_paths(investigation_id, report_dir_path, export_dir_path)
    report_html = build_report_html_document(markdown, investigation_id=investigation_id, generated_at=generated_at)
    report = InvestigationReport(
        investigation_id=investigation_id,
        source_url=source_url,
        mission_text=mission_text,
        date_start=date_start,
        date_end=date_end,
        strategy=strategy,
        mission_context=mission_context,
        links_found=len(raw_links),
        documents_analyzed=len(documents),
        findings=findings,
        limitations=limitations,
        evidence_links=evidence_links,
        markdown=markdown,
        markdown_path=str(paths["markdown"]),
        report_markdown_path=str(paths["markdown"]),
        report_html_path=str(paths["html"]),
        csv_path=str(paths["csv"]),
        json_path=str(paths["json"]),
        zip_path=str(paths["zip"]),
        used_deepseek=used_deepseek,
        metrics=metrics,
        totals=totals,
        generated_at=generated_at,
        report_html=report_html,
    )
    save_dossier_files(report, paths)
    return report


def validate_source_url(source_url: str) -> str:
    parsed = urlsplit((source_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url deve ser uma URL http(s) valida.")
    return source_url.strip()


def fetch_url(url: str, *, timeout_seconds: float = 20.0) -> FetchResult:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "HERMES/0.1", "Accept": "text/html,application/pdf,*/*;q=0.8"})
        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "text": response.text if "pdf" not in (response.headers.get("content-type") or "").lower() else "",
            "content": response.content,
            "error": None,
        }
    except Exception as exc:
        return {"url": url, "status_code": None, "content_type": None, "text": "", "content": b"", "error": f"{exc.__class__.__name__}: {exc}"}


def response_text(response: FetchResult) -> str:
    if response.get("text"):
        return str(response["text"])
    content = response.get("content") or b""
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return str(content or "")


def discover_gazette_links(raw_links: list[dict[str, Any]], *, date_start: str | None, date_end: str | None, limit: int) -> list[GazetteLink]:
    start = parse_date(date_start)
    end = parse_date(date_end)
    links: list[GazetteLink] = []
    for raw in raw_links:
        haystack = f"{raw.get('url', '')} {raw.get('text', '')}".lower()
        score = sum(1 for term in LINK_PRIORITY_TERMS if term in haystack)
        is_pdf = bool(raw.get("is_pdf")) or is_pdf_url(str(raw.get("url") or "")) or "pdf" in haystack
        if not score and not is_pdf:
            continue
        date_value = extract_date_from_text(haystack)
        if date_value and start and date_value < start:
            continue
        if date_value and end and date_value > end:
            continue
        links.append(
            GazetteLink(
                url=str(raw.get("url")),
                text=str(raw.get("text") or raw.get("url")),
                is_pdf=is_pdf,
                date=date_value.isoformat() if date_value else None,
                date_unknown=date_value is None,
                priority_score=score + (2 if is_pdf else 0),
            )
        )
    links.sort(key=lambda item: item.priority_score, reverse=True)
    return links[:limit]


def fetch_document(link: GazetteLink, fetcher: Fetcher) -> GazetteDocument:
    response = fetcher(link.url)
    content_type = response.get("content_type") or ""
    is_pdf = link.is_pdf or "pdf" in content_type.lower()
    limitations: list[str] = []
    text = ""
    if response.get("error"):
        limitations.append(f"Falha ao baixar {link.url}: {response['error']}")
    elif is_pdf:
        text, pdf_limitation = extract_pdf_text(response.get("content") or b"")
        if pdf_limitation:
            limitations.append(f"{link.url}: {pdf_limitation}")
    else:
        text = extract_visible_text(response_text(response), limit=MAX_DOCUMENT_CHARS)
        if not text:
            limitations.append(f"{link.url}: HTML sem texto visivel extraivel.")
    return GazetteDocument(
        url=link.url,
        title=link.text,
        content_type=content_type,
        is_pdf=is_pdf,
        date=link.date,
        text=text[:MAX_DOCUMENT_CHARS],
        limitations=limitations,
    )


def extract_pdf_text(content: Any) -> tuple[str, str | None]:
    if not isinstance(content, bytes) or not content:
        return "", "PDF sem conteudo baixado."
    try:
        from pypdf import PdfReader
    except Exception:
        return "", "Biblioteca pypdf indisponivel; OCR/PDF fica para etapa futura."
    try:
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
        if not text.strip():
            return "", "PDF sem texto extraivel; pode ser imagem. OCR nao implementado neste GOAL."
        return clean_text(text)[:MAX_DOCUMENT_CHARS], None
    except Exception as exc:
        return "", f"falha ao extrair PDF ({exc.__class__.__name__})."


def build_mission_context(mission_text: str) -> dict[str, Any]:
    mission_terms = extract_mission_terms(mission_text)
    all_terms = dedupe_strings(mission_terms + DEFAULT_TERMS)
    return {
        "mission_text": mission_text,
        "termos_principais": mission_terms,
        "termos_expandidos": all_terms,
        "tipos_evento_interesse": ["licitacao", "contrato", "aditivo", "homologacao", "dispensa"],
        "natureza_objeto_interesse": ["obras_engenharia", "manutencao", "servicos"],
        "periodo_identificado": None,
        "query_humana_resumida": mission_text[:200],
        "all_terms": all_terms,
    }


def merge_deepseek_terms(context: dict[str, Any], expanded: dict[str, Any]) -> None:
    for key in ("termos_principais", "termos_expandidos", "tipos_evento_interesse", "natureza_objeto_interesse"):
        values = expanded.get(key)
        if isinstance(values, list):
            context[key] = dedupe_strings([str(item) for item in values] + list(context.get(key, [])))
    if expanded.get("periodo_identificado"):
        context["periodo_identificado"] = expanded["periodo_identificado"]
    if expanded.get("query_humana_resumida"):
        context["query_humana_resumida"] = str(expanded["query_humana_resumida"])
    context["all_terms"] = dedupe_strings(context.get("termos_principais", []) + context.get("termos_expandidos", []) + DEFAULT_TERMS)


def extract_mission_terms(mission_text: str) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", mission_text.lower())
    stopwords = {"para", "com", "dos", "das", "que", "uma", "por", "sobre", "entre", "quais", "qual"}
    return dedupe_strings([word for word in words if word not in stopwords])


def build_relevant_chunks(documents: list[GazetteDocument], terms: list[str]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for document in documents:
        text = document.text or ""
        if not text:
            continue
        lower = text.lower()
        matches = [term for term in terms if term.lower() in lower]
        if matches:
            for term in matches[:5]:
                idx = lower.find(term.lower())
                start = max(0, idx - 900)
                end = min(len(text), idx + MAX_CHARS_PER_CHUNK)
                chunks.append({"document": document, "snippet": text[start:end], "matched_terms": matches})
        else:
            chunks.append({"document": document, "snippet": text[:1200], "matched_terms": []})
    return chunks


def dedupe_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for chunk in chunks:
        key = stable_hash(" ".join(chunk["snippet"].lower().split())[:900])
        if key in seen:
            continue
        seen.add(key)
        result.append(chunk)
    return result


def deterministic_classify_chunk(chunk: dict[str, Any], terms: list[str]) -> GazetteFinding:
    snippet = chunk["snippet"]
    lower = snippet.lower()
    matched = [term for term in terms if term.lower() in lower][:12]
    event_type = detect_event_type(lower)
    natureza = detect_natureza(lower)
    score = min(100, 20 + len(matched) * 7 + (20 if event_type != "outro" else 0) + (15 if natureza != "outro" else 0))
    document: GazetteDocument = chunk["document"]
    return GazetteFinding(
        title=document.title,
        date=document.date,
        event_type=event_type,
        natureza=natureza,
        score=score if matched else 0,
        agency=extract_regex(snippet, r"(?:órgão|orgao|secretaria|prefeitura)[:\s-]+([A-ZÀ-Úa-zà-ú0-9 .,/()-]{4,100})"),
        company_name=extract_regex(snippet, r"(?:empresa|contratada|fornecedor)[:\s-]+([A-ZÀ-Ú0-9 .,&/-]{4,120})"),
        process_number=extract_regex(snippet, r"(?:processo|proc\.?)\s*(?:n[ºo]\.?)?\s*([0-9][0-9./-]{4,})"),
        contract_number=extract_regex(snippet, r"(?:contrato|ct)\s*(?:n[ºo]\.?)?\s*([0-9][0-9./-]{2,})"),
        value_text=extract_regex(snippet, r"(R\$\s*[0-9.\,]+)"),
        object_text=extract_object_text(snippet),
        summary=summarize_snippet(snippet),
        reason="Trecho selecionado por termos da missão e termos padrão de atos oficiais.",
        matched_terms=matched,
        snippet=snippet[:900],
        link=document.url,
    )


def finding_from_classification(chunk: dict[str, Any], data: dict[str, Any]) -> GazetteFinding:
    fallback = deterministic_classify_chunk(chunk, chunk.get("matched_terms") or [])
    document: GazetteDocument = chunk["document"]
    return GazetteFinding(
        title=document.title,
        date=document.date,
        event_type=str(data.get("event_type") or fallback.event_type),
        natureza=str(data.get("natureza_objeto") or data.get("natureza") or fallback.natureza),
        score=int(data.get("relevance_score") or fallback.score),
        agency=none_or_str(data.get("agency")) or fallback.agency,
        company_name=none_or_str(data.get("company_name")) or fallback.company_name,
        process_number=none_or_str(data.get("process_number")) or fallback.process_number,
        contract_number=none_or_str(data.get("contract_number")) or fallback.contract_number,
        value_text=none_or_str(data.get("value_text")) or fallback.value_text,
        object_text=none_or_str(data.get("object_text")) or fallback.object_text,
        summary=none_or_str(data.get("summary")) or fallback.summary,
        reason=none_or_str(data.get("reason")) or fallback.reason,
        matched_terms=[str(item) for item in data.get("matched_terms") or fallback.matched_terms],
        snippet=chunk["snippet"][:900],
        link=document.url,
    )


def detect_event_type(lower: str) -> str:
    mapping = [
        ("ata de registro", "ata_registro_precos"),
        ("termo aditivo", "aditivo"),
        ("aditivo", "aditivo"),
        ("homolog", "homologacao"),
        ("adjudic", "adjudicacao"),
        ("dispensa", "dispensa"),
        ("inexigibilidade", "inexigibilidade"),
        ("reajuste", "reajuste"),
        ("prorrog", "prorrogacao"),
        ("reequil", "reequilibrio"),
        ("rescis", "rescisao"),
        ("contrato", "contrato"),
        ("edital", "edital"),
        ("licit", "licitacao"),
    ]
    for needle, event in mapping:
        if needle in lower:
            return event
    return "outro"


def detect_natureza(lower: str) -> str:
    if any(term in lower for term in ("obra", "engenharia", "pavimenta", "drenagem", "infraestrutura", "projeto executivo", "fiscaliza")):
        return "obras_engenharia"
    if any(term in lower for term in ("manutenc", "reforma", "conserva")):
        return "manutencao"
    if "saúde" in lower or "saude" in lower:
        return "saude"
    if "educa" in lower or "escola" in lower:
        return "educacao"
    if "transporte" in lower:
        return "transporte"
    if "serviço" in lower or "servico" in lower:
        return "servicos"
    if "compra" in lower or "aquisição" in lower or "aquisicao" in lower:
        return "compras"
    return "outro"


def extract_regex(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return clean_text(match.group(1))[:160]


def extract_object_text(text: str) -> str | None:
    match = re.search(r"(?:objeto|descrição|descricao)[:\s-]+(.{20,260})", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return clean_text(match.group(1))[:260]
    return summarize_snippet(text)


def summarize_snippet(snippet: str) -> str:
    text = clean_text(snippet)
    return text[:320] + ("..." if len(text) > 320 else "")


def describe_strategy(content_type: str, links: list[GazetteLink], documents: list[GazetteDocument], used_deepseek: bool) -> str:
    pdf_count = sum(1 for item in links if item.is_pdf)
    html_count = sum(1 for item in documents if not item.is_pdf)
    ai = "DeepSeek + fallback deterministico" if used_deepseek else "fallback deterministico"
    return f"Inspecao HTML inicial, priorizacao de links oficiais/PDFs ({pdf_count} PDFs), analise de {html_count} HTMLs e classificacao por {ai}."


def build_report_input(**kwargs: Any) -> dict[str, Any]:
    documents = kwargs.pop("documents")
    findings = kwargs.pop("findings")
    return {
        **kwargs,
        "documents_analyzed": len(documents),
        "findings": [asdict(finding) for finding in findings],
        "evidence_links": dedupe_strings([finding.link for finding in findings] + [doc.url for doc in documents]),
    }


def deterministic_report_markdown(report_input: dict[str, Any]) -> str:
    findings = report_input.get("findings", [])
    limitations = report_input.get("limitations", [])
    evidence_links = report_input.get("evidence_links", [])
    lines = [
        "# Relatório HERMES — Investigação de Diário Oficial",
        "",
        "## 1. Missão",
        str(report_input.get("mission_text") or "-"),
        "",
        "## 2. Fonte analisada",
        str(report_input.get("source_url") or "-"),
        "",
        "## 3. Período informado",
        f"{report_input.get('date_start') or 'não informado'} a {report_input.get('date_end') or 'não informado'}",
        "",
        "## 4. Estratégia usada",
        str(report_input.get("strategy") or "-"),
        "",
        "## 5. Resumo executivo",
        build_executive_summary(report_input),
        "",
        "## 6. Principais achados",
    ]
    if findings:
        for index, finding in enumerate(findings, start=1):
            lines.extend(
                [
                    f"### Achado {index}: {finding.get('title') or 'Publicação relevante'}",
                    f"- Data: {finding.get('date') or 'data desconhecida'}",
                    f"- Tipo de evento: {finding.get('event_type')}",
                    f"- Natureza: {finding.get('natureza')}",
                    f"- Score: {finding.get('score')}",
                    f"- Órgão: {finding.get('agency') or '-'}",
                    f"- Empresa: {finding.get('company_name') or '-'}",
                    f"- Processo/Contrato: {finding.get('process_number') or '-'} / {finding.get('contract_number') or '-'}",
                    f"- Valor: {finding.get('value_text') or '-'}",
                    f"- Termos encontrados: {', '.join(finding.get('matched_terms') or []) or '-'}",
                    f"- Trecho relevante: {finding.get('snippet') or '-'}",
                    f"- Link da fonte: {finding.get('link')}",
                    "",
                ]
            )
    else:
        lines.extend(["Nenhum achado relevante foi classificado no recorte analisado.", ""])
    lines.extend(
        [
            "## 7. Publicações analisadas",
            f"- Total de links encontrados: {report_input.get('links_found')}",
            f"- Total de documentos analisados: {report_input.get('documents_analyzed')}",
            f"- Total de achados relevantes: {len(findings)}",
            "",
            "## 8. Evidências",
        ]
    )
    lines.extend([f"- {link}" for link in evidence_links] or ["- Nenhuma evidência com link."])
    lines.extend(["", "## 9. Limitações"])
    lines.extend([f"- {item}" for item in dedupe_strings(limitations)] or ["- Nenhuma limitação registrada."])
    lines.extend(
        [
            "",
            "## 10. Próximas ações",
            "- Ativar monitoramento diário da fonte.",
            "- Cruzar achados com PNCP e bases PMSP/TCE-SP.",
            "- Usar Playwright se a página depender de JavaScript.",
            "- Rodar OCR futuramente se PDFs forem imagem.",
            "",
        ]
    )
    return "\n".join(lines)


def build_executive_summary(report_input: dict[str, Any]) -> str:
    findings = report_input.get("findings", [])
    if not findings:
        return "A fonte foi analisada, mas nenhum achado relevante foi confirmado no recorte e período informados."
    top = findings[0]
    return (
        f"Foram identificados {len(findings)} achados relevantes em {report_input.get('documents_analyzed')} documentos analisados. "
        f"O achado mais relevante foi classificado como {top.get('event_type')} / {top.get('natureza')} com score {top.get('score')}. "
        "Os links das evidências foram preservados para auditoria."
    )


def resolve_export_dir(report_dir: Path, export_dir: Path | str | None) -> Path:
    if export_dir is not None:
        return Path(export_dir)
    if report_dir.name == "reports":
        return report_dir.parent / "exports"
    return report_dir / "exports"


def create_investigation_id(report_dir: Path, export_dir: Path, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"hermes_diario_{timestamp}"
    for suffix in [""] + [f"_{index:02d}" for index in range(2, 100)]:
        candidate = f"{base}{suffix}"
        paths = build_dossier_paths(candidate, report_dir, export_dir)
        if not any(path.exists() for path in paths.values()):
            return candidate
    return f"{base}_{datetime.now().strftime('%f')}"


def build_dossier_paths(investigation_id: str, report_dir: Path, export_dir: Path) -> dict[str, Path]:
    return {
        "markdown": report_dir / f"{investigation_id}.md",
        "html": report_dir / f"{investigation_id}.html",
        "csv": export_dir / f"{investigation_id}_achados.csv",
        "json": export_dir / f"{investigation_id}.json",
        "zip": export_dir / f"{investigation_id}_dossie.zip",
    }


def save_dossier_files(report: InvestigationReport, paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["markdown"].write_text(report.markdown.rstrip() + "\n", encoding="utf-8")
    paths["html"].write_text(report.report_html, encoding="utf-8")
    write_findings_csv(report.findings, paths["csv"])
    paths["json"].write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(paths["zip"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in ("markdown", "html", "csv", "json"):
            archive.write(paths[key], arcname=paths[key].name)


def write_findings_csv(findings: list[GazetteFinding], path: Path) -> None:
    fieldnames = [
        "titulo",
        "data",
        "tipo_evento",
        "natureza",
        "score",
        "orgao",
        "empresa",
        "processo",
        "contrato",
        "valor",
        "termos_encontrados",
        "trecho",
        "link_fonte",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            writer.writerow(
                {
                    "titulo": finding.title,
                    "data": finding.date or "",
                    "tipo_evento": finding.event_type,
                    "natureza": finding.natureza,
                    "score": finding.score,
                    "orgao": finding.agency or "",
                    "empresa": finding.company_name or "",
                    "processo": finding.process_number or "",
                    "contrato": finding.contract_number or "",
                    "valor": finding.value_text or "",
                    "termos_encontrados": "; ".join(finding.matched_terms),
                    "trecho": finding.snippet,
                    "link_fonte": finding.link,
                }
            )


def build_report_html_document(markdown: str, *, investigation_id: str, generated_at: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório HERMES — {escape(investigation_id)}</title>
  <style>
    :root {{ color-scheme: light; --text: #1f2933; --muted: #5b6673; --line: #d9dee5; --bg: #f6f7f9; --panel: #ffffff; --primary: #1f6feb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Arial, Helvetica, sans-serif; line-height: 1.55; }}
    main {{ width: min(920px, calc(100vw - 32px)); margin: 32px auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 32px; box-shadow: 0 1px 2px rgba(20, 28, 38, 0.06); }}
    h1 {{ margin-top: 0; font-size: 30px; }}
    h2 {{ margin-top: 30px; padding-top: 18px; border-top: 1px solid var(--line); font-size: 22px; }}
    h3 {{ margin-top: 22px; font-size: 18px; }}
    a {{ color: var(--primary); overflow-wrap: anywhere; }}
    li {{ margin: 7px 0; }}
    .meta {{ margin: 0 0 24px; color: var(--muted); }}
    @media print {{ body {{ background: #fff; }} main {{ width: auto; margin: 0; border: 0; box-shadow: none; }} a {{ color: #000; }} }}
  </style>
</head>
<body>
  <main>
    <p class="meta">ID da investigação: {escape(investigation_id)} · Gerado em {escape(generated_at)}</p>
    {markdown_to_html(markdown)}
  </main>
</body>
</html>"""


def markdown_to_html(markdown: str) -> str:
    html_parts: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h3>{render_inline_markdown(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h2>{render_inline_markdown(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h1>{render_inline_markdown(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{render_inline_markdown(line[2:])}</li>")
        elif line.startswith("> "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<blockquote>{render_inline_markdown(line[2:])}</blockquote>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{render_inline_markdown(line)}</p>")
    if in_list:
        html_parts.append("</ul>")
    return "\n".join(html_parts)


def render_inline_markdown(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda match: f'<a href="{match.group(2)}" target="_blank" rel="noopener">{match.group(1)}</a>',
        escaped,
    )
    return re.sub(
        r"(?<![\"'>])(https?://[^\s<]+)",
        lambda match: f'<a href="{match.group(1)}" target="_blank" rel="noopener">{match.group(1)}</a>',
        escaped,
    )


def save_markdown_report(markdown: str, report_dir: Path | str) -> Path:
    directory = Path(report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"hermes_diario_oficial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text(markdown + "\n", encoding="utf-8")
    return path


def parse_date(value: str | None):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def extract_date_from_text(value: str):
    text = value or ""
    patterns = [
        (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"),
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return datetime.strptime(match.group(0), fmt).date()
            except ValueError:
                continue
    return None


def none_or_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
