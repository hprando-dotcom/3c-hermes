from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import httpx

DOE_TCESP_BASE_URL = "https://doe.tce.sp.gov.br/pdf"
DEFAULT_RAW_DIR = Path("data/raw/doe_tcesp")

FetchResult = dict[str, Any]
Fetcher = Callable[[str], FetchResult]


@dataclass(slots=True)
class DoeTcespPageMetadata:
    page_number: int
    footer_page: int | None = None
    edition: str | None = None
    availability_date: str | None = None
    publication_date: str | None = None


@dataclass(slots=True)
class DoeTcespPageText:
    page_number: int
    text: str
    text_path: str | None
    metadata: DoeTcespPageMetadata


@dataclass(slots=True)
class DoeTcespPdfCandidate:
    date: str
    url: str
    status: str
    status_code: int | None = None
    raw_pdf_path: str | None = None
    document_hash: str | None = None
    pages_count: int = 0
    page_text_paths: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class DoeTcespTermResult:
    term: str
    status: str
    found: bool
    pdf_url: str | None
    page: int | None
    page_link: str | None
    snippet: str | None
    issue_date: str | None
    edition: str | None
    availability_date: str | None
    publication_date: str | None
    raw_pdf_path: str | None
    text_path: str | None
    pdfs_consultados: list[str]
    period_start: str
    period_end: str
    motivo: str | None = None
    occurrences: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class DoeTcespSearchReport:
    source: str
    date_start: str
    date_end: str
    terms: list[str]
    candidates: list[DoeTcespPdfCandidate]
    results: list[DoeTcespTermResult]
    raw_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "terms": self.terms,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "results": [asdict(result) for result in self.results],
            "raw_dir": self.raw_dir,
        }


class DoeTcespPdfConnector:
    def __init__(
        self,
        *,
        raw_dir: Path | str = DEFAULT_RAW_DIR,
        fetcher: Fetcher | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.fetcher = fetcher
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        *,
        date_start: str | date | None,
        date_end: str | date | None,
        terms: list[str],
        limit: int | None = None,
    ) -> DoeTcespSearchReport:
        start, end = parse_period(date_start, date_end)
        normalized_terms = dedupe_terms(terms)
        candidate_dates = list(iter_date_range(start, end))
        if limit:
            candidate_dates = candidate_dates[: max(1, int(limit))]

        candidates: list[DoeTcespPdfCandidate] = []
        pages_by_pdf: list[tuple[DoeTcespPdfCandidate, list[DoeTcespPageText]]] = []

        for candidate_date in candidate_dates:
            candidate, pages = self._collect_candidate(candidate_date)
            candidates.append(candidate)
            if pages:
                pages_by_pdf.append((candidate, pages))

        pdfs_consultados = [candidate.url for candidate in candidates]
        results = [
            self._result_for_term(
                term,
                pages_by_pdf=pages_by_pdf,
                pdfs_consultados=pdfs_consultados,
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                candidates=candidates,
                all_terms=normalized_terms,
            )
            for term in normalized_terms
        ]

        return DoeTcespSearchReport(
            source="DOE-TCESP",
            date_start=start.isoformat(),
            date_end=end.isoformat(),
            terms=normalized_terms,
            candidates=candidates,
            results=results,
            raw_dir=str(self.raw_dir),
        )

    def _collect_candidate(self, candidate_date: date) -> tuple[DoeTcespPdfCandidate, list[DoeTcespPageText]]:
        url = build_doe_tcesp_pdf_url(candidate_date)
        response = self._fetch(url)
        status_code = response.get("status_code")
        candidate = DoeTcespPdfCandidate(date=candidate_date.isoformat(), url=url, status="nao_encontrado", status_code=status_code)

        if response.get("error"):
            candidate.status = "erro"
            candidate.error = str(response["error"])
            return candidate, []

        if status_code == 404:
            return candidate, []

        if isinstance(status_code, int) and status_code >= 400:
            candidate.status = "erro"
            candidate.error = f"HTTP {status_code}"
            return candidate, []

        content = response.get("content") or b""
        content_type = str(response.get("content_type") or "").lower()
        if not isinstance(content, bytes) or not content:
            candidate.status = "erro"
            candidate.error = "PDF sem conteudo baixado."
            return candidate, []
        if "pdf" not in content_type and not content.startswith(b"%PDF"):
            candidate.status = "erro"
            candidate.error = f"Resposta nao parece PDF ({content_type or 'content-type ausente'})."
            return candidate, []

        raw_pdf_path = self._raw_pdf_path(candidate_date)
        raw_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        raw_pdf_path.write_bytes(content)
        candidate.status = "baixado"
        candidate.raw_pdf_path = str(raw_pdf_path)
        candidate.document_hash = hashlib.sha256(content).hexdigest()

        try:
            raw_pages = self._extract_pdf_pages(content)
        except Exception as exc:
            candidate.status = "erro"
            candidate.error = f"falha ao extrair PDF ({exc.__class__.__name__}: {exc})"
            return candidate, []

        pages: list[DoeTcespPageText] = []
        page_dir = raw_pdf_path.parent / "pages"
        page_dir.mkdir(parents=True, exist_ok=True)
        for index, text in enumerate(raw_pages, start=1):
            metadata = extract_page_metadata(text or "", page_number=index)
            human_page_number = metadata.footer_page or index
            metadata.page_number = human_page_number
            text_path = page_dir / f"page_{human_page_number:03d}.txt"
            text_path.write_text(text or "", encoding="utf-8")
            pages.append(DoeTcespPageText(page_number=human_page_number, text=text or "", text_path=str(text_path), metadata=metadata))
            candidate.page_text_paths.append(str(text_path))
        candidate.pages_count = len(pages)
        return candidate, pages

    def _fetch(self, url: str) -> FetchResult:
        if self.fetcher is not None:
            return self.fetcher(url)
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "HERMES/0.2",
                        "Accept": "application/pdf,*/*;q=0.8",
                    },
                )
            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content": response.content,
                "text": "",
                "error": None,
            }
        except Exception as exc:
            return {
                "url": url,
                "status_code": None,
                "content_type": None,
                "content": b"",
                "text": "",
                "error": f"{exc.__class__.__name__}: {exc}",
            }

    def _extract_pdf_pages(self, content: bytes) -> list[str]:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        return [page.extract_text() or "" for page in reader.pages]

    def _raw_pdf_path(self, candidate_date: date) -> Path:
        return (
            self.raw_dir
            / f"{candidate_date:%Y}"
            / f"{candidate_date:%m}"
            / f"{candidate_date:%d}"
            / f"doe-tce-{candidate_date:%Y-%m-%d}.pdf"
        )

    def _result_for_term(
        self,
        term: str,
        *,
        pages_by_pdf: list[tuple[DoeTcespPdfCandidate, list[DoeTcespPageText]]],
        pdfs_consultados: list[str],
        period_start: str,
        period_end: str,
        candidates: list[DoeTcespPdfCandidate],
        all_terms: list[str],
    ) -> DoeTcespTermResult:
        occurrences: list[dict[str, Any]] = []
        for candidate, pages in pages_by_pdf:
            for page in pages:
                snippet = find_term_snippet(page.text, term)
                if snippet is None:
                    continue
                context_terms = [other for other in all_terms if other != term and find_term_snippet(page.text, other, radius=80) is not None]
                page_link = f"{candidate.url}#page={page.page_number}"
                occurrence = {
                    "term": term,
                    "pdf_url": candidate.url,
                    "page": page.page_number,
                    "page_link": page_link,
                    "snippet": snippet,
                    "issue_date": candidate.date,
                    "edition": page.metadata.edition,
                    "availability_date": page.metadata.availability_date,
                    "publication_date": page.metadata.publication_date,
                    "raw_pdf_path": candidate.raw_pdf_path,
                    "text_path": page.text_path,
                    "document_hash": candidate.document_hash,
                    "context_terms": context_terms,
                    "context_score": len(context_terms),
                }
                occurrences.append(occurrence)

        if occurrences:
            occurrences.sort(key=lambda item: (int(item.get("context_score") or 0), str(item.get("issue_date") or ""), -int(item.get("page") or 0)), reverse=True)
            first = occurrences[0]
            return DoeTcespTermResult(
                term=term,
                status="encontrado",
                found=True,
                pdf_url=first["pdf_url"],
                page=first["page"],
                page_link=first["page_link"],
                snippet=first["snippet"],
                issue_date=first["issue_date"],
                edition=first["edition"],
                availability_date=first["availability_date"],
                publication_date=first["publication_date"],
                raw_pdf_path=first["raw_pdf_path"],
                text_path=first["text_path"],
                pdfs_consultados=pdfs_consultados,
                period_start=period_start,
                period_end=period_end,
                occurrences=occurrences,
            )

        downloaded = [candidate for candidate in candidates if candidate.status == "baixado"]
        errors = [candidate for candidate in candidates if candidate.status == "erro"]
        if errors and not downloaded:
            status = "erro"
            motivo = "Nenhum PDF foi extraido com sucesso; houve erro nas consultas."
        else:
            status = "nao_encontrado"
            motivo = "Termo/processo nao localizado nos PDFs diarios consultados."
        return DoeTcespTermResult(
            term=term,
            status=status,
            found=False,
            pdf_url=None,
            page=None,
            page_link=None,
            snippet=None,
            issue_date=None,
            edition=None,
            availability_date=None,
            publication_date=None,
            raw_pdf_path=None,
            text_path=None,
            pdfs_consultados=pdfs_consultados,
            period_start=period_start,
            period_end=period_end,
            motivo=motivo,
        )


def build_doe_tcesp_pdf_url(value: date) -> str:
    return f"{DOE_TCESP_BASE_URL}/{value:%Y}/{value:%m}/doe-tce-{value:%Y-%m-%d}.pdf"


def parse_period(date_start: str | date | None, date_end: str | date | None) -> tuple[date, date]:
    start = parse_date_value(date_start) or datetime.now().date()
    end = parse_date_value(date_end) or start
    if end < start:
        raise ValueError("date_end nao pode ser anterior a date_start.")
    return start, end


def parse_date_value(value: str | date | None) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def iter_date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def extract_page_metadata(text: str, *, page_number: int) -> DoeTcespPageMetadata:
    compact = clean_text(text)
    edition = None
    edition_match = re.search(r"(\d+\s*[ªa]?\s+edi[cç][aã]o)", compact, flags=re.IGNORECASE)
    if edition_match:
        edition = clean_text(edition_match.group(1))

    normalized = strip_accents(compact)
    availability_date = extract_labeled_date(normalized, "Disponibilizacao")
    publication_date = extract_labeled_date(normalized, "Publicacao")

    footer_page = None
    footer_match = re.search(r"(?:^|\s)(\d{1,4})\s*[\u2013\u2014-]\s*\d+\s*[ªa]?\s+edi", compact, flags=re.IGNORECASE)
    if footer_match:
        try:
            footer_page = int(footer_match.group(1))
        except ValueError:
            footer_page = None

    return DoeTcespPageMetadata(
        page_number=page_number,
        footer_page=footer_page,
        edition=edition,
        availability_date=availability_date,
        publication_date=publication_date,
    )


def extract_labeled_date(text: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*:\s*(\d{{2}}/\d{{2}}/\d{{4}})", text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def find_term_snippet(text: str, term: str, *, radius: int = 500) -> str | None:
    clean = clean_text(text)
    if not clean or not term:
        return None
    index = clean.casefold().find(term.casefold())
    if index < 0:
        index = strip_accents(clean).casefold().find(strip_accents(term).casefold())
    if index < 0:
        return None
    start = max(0, index - radius)
    end = min(len(clean), index + len(term) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end]}{suffix}"


def dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        text = clean_text(term)
        key = strip_accents(text).casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def strip_accents(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(char))
