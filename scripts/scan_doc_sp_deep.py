from __future__ import annotations

import json
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hermes.connectors.doc_sp.auth import ApilibAuthError, ApilibAuthenticator, ApilibCredentials, mask_secret, safe_preview

METHODS = ("GET", "HEAD", "OPTIONS")

BASE_URLS = (
    "https://gateway.apilib.prefeitura.sp.gov.br",
    "https://gateway.apilib.prefeitura.sp.gov.br/sg",
    "https://gateway.apilib.prefeitura.sp.gov.br/sg/dom",
    "https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1",
    "https://gateway.apilib.prefeitura.sp.gov.br/dom",
    "https://gateway.apilib.prefeitura.sp.gov.br/dom/v1",
    "https://gateway.apilib.prefeitura.sp.gov.br/diario-oficial",
    "https://gateway.apilib.prefeitura.sp.gov.br/diario-oficial/v1",
    "https://gateway.apilib.prefeitura.sp.gov.br/Diario_Oficial",
    "https://gateway.apilib.prefeitura.sp.gov.br/Diario_Oficial/v1",
)

PATHS = (
    "/swagger",
    "/swagger.json",
    "/openapi.json",
    "/api-docs",
    "/v2/api-docs",
    "/v3/api-docs",
    "/services",
    "/metadata",
    "/health",
    "/status",
    "/version",
    "/Publicacao",
    "/Publicacoes",
    "/publicacao",
    "/publicacoes",
    "/Licitacao",
    "/Licitacoes",
    "/licitacao",
    "/licitacoes",
    "/Materia",
    "/Materias",
    "/materia",
    "/materias",
    "/Consulta",
    "/Pesquisa",
    "/Busca",
    "/Edicao",
    "/Edicoes",
    "/Caderno",
    "/Cadernos",
)

INTERESTING_STATUSES = {200, 201, 204, 401, 403, 405}
INTERESTING_KEYWORDS = ("swagger", "openapi", "publicacao", "licitacao", "diario", "materia", "caderno")


@dataclass(slots=True)
class DeepScanProbe:
    base_url: str
    path: str
    url: str
    method: str
    status: int | None
    content_type: str | None
    elapsed_ms: float
    response_size: int
    preview: str
    looks_wso2: bool
    looks_html_iis: bool
    looks_json: bool
    keyword_hits: list[str] = field(default_factory=list)
    interesting: bool = False
    interesting_reasons: list[str] = field(default_factory=list)
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "path": self.path,
            "url": self.url,
            "method": self.method,
            "status": self.status,
            "content_type": self.content_type,
            "elapsed_ms": self.elapsed_ms,
            "response_size": self.response_size,
            "preview": self.preview,
            "looks_wso2": self.looks_wso2,
            "looks_html_iis": self.looks_html_iis,
            "looks_json": self.looks_json,
            "keyword_hits": self.keyword_hits,
            "interesting": self.interesting,
            "interesting_reasons": self.interesting_reasons,
            "error": self.error,
        }


class DeepScanReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"doc_sp_deep_scan_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"doc_sp_deep_scan_summary_{self.timestamp}.json"

    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line)

    def save_log(self) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return self.log_path

    def save_summary(self, summary: dict[str, Any]) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self.summary_path


def main() -> int:
    report = DeepScanReport(PROJECT_ROOT / "logs")
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    probes: list[DeepScanProbe] = []
    summary: dict[str, Any] | None = None

    report.emit("HERMES - Scanner profundo DOC SP / APILIB")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Arquivo .env carregado: {env_path.exists()}")
    report.emit(f"Metodos: {', '.join(METHODS)}")
    report.emit(f"Bases: {len(BASE_URLS)}")
    report.emit(f"Paths: {len(PATHS)}")
    report.emit(f"Total planejado: {len(METHODS) * len(BASE_URLS) * len(PATHS)} chamadas")
    report.emit("")

    try:
        credentials = ApilibCredentials.from_env()
        secrets = [credentials.consumer_key, credentials.consumer_secret]

        report.emit("Credenciais:")
        report.emit(f"- SP_DOE_CONSUMER_KEY: {mask_secret(credentials.consumer_key, visible=6)}")
        report.emit("- SP_DOE_CONSUMER_SECRET: <configured, not printed>")
        report.emit("")

        report.emit("Autenticacao OAuth2 client_credentials:")
        auth_result = ApilibAuthenticator(credentials).request_token()
        for attempt in auth_result.attempts:
            report.emit(format_auth_attempt(attempt, secrets))

        token = auth_result.token
        secrets.append(token.access_token)

        report.emit(f"Token obtido via: {token.token_url}")
        report.emit(f"Token type: {token.token_type}")
        report.emit(f"Access token: {token.masked_access_token}")
        report.emit(f"Expires in: {token.expires_in}")
        report.emit("")

        probes = run_deep_scan(token.access_token, secrets=secrets, report=report)
        summary = build_summary(report, token, probes)

        report.emit("")
        report.emit("Resumo final:")
        report.emit(f"- Chamadas executadas: {len(probes)}")
        report.emit(f"- Distribuicao de status: {format_status_counts(summary['status_counts'])}")
        report.emit(f"- Candidatos interessantes: {summary['interesting_count']}")
        report.emit(f"- WSO2 detectado em respostas: {'sim' if summary['wso2_detected'] else 'nao'}")
        report.emit(f"- HTML IIS detectado em respostas: {'sim' if summary['html_iis_detected'] else 'nao'}")
        report.emit(f"- JSON detectado em respostas: {'sim' if summary['json_detected'] else 'nao'}")

        for candidate in summary["candidates"][:20]:
            report.emit(
                "- Candidato: "
                f"{candidate['method']} {candidate['url']} | status={candidate['status']} | "
                f"content-type={candidate['content_type']} | reasons={candidate['interesting_reasons']}"
            )

        return 0
    except ApilibAuthError as exc:
        report.emit(f"Falha de autenticacao: {exc}")
        for attempt in exc.attempts:
            report.emit(format_auth_attempt(attempt, []))
        return 2
    except Exception as exc:
        report.emit(f"Falha inesperada: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        if summary is None:
            summary = build_failure_summary(report, probes)
        summary_path = report.save_summary(summary)
        log_path = report.save_log()
        print(f"Relatorio salvo em: {log_path}")
        print(f"Resumo JSON salvo em: {summary_path}")


def run_deep_scan(access_token: str, secrets: list[str], report: DeepScanReport) -> list[DeepScanProbe]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    probes: list[DeepScanProbe] = []

    report.emit("Headers de scan:")
    report.emit("- Authorization: Bearer <redacted>")
    report.emit("- Accept: application/json")
    report.emit("- Content-Type: application/json")
    report.emit("")
    report.emit("Probes:")

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for base_url in BASE_URLS:
            for path in PATHS:
                url = build_url(base_url, path)
                for method in METHODS:
                    probe = execute_probe(client, method, base_url, path, url, headers, secrets)
                    probes.append(probe)
                    report.emit(format_probe(probe))

    return probes


def execute_probe(
    client: httpx.Client,
    method: str,
    base_url: str,
    path: str,
    url: str,
    headers: dict[str, str],
    secrets: list[str],
) -> DeepScanProbe:
    started = perf_counter()

    try:
        response = client.request(method, url, headers=headers)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        body_text = response.text if response.content else ""
        preview = masked_preview(body_text, secrets)
        keyword_hits = detect_keywords(body_text)
        looks_json = detect_json(response, body_text)
        looks_wso2 = detect_wso2(response, body_text)
        looks_html_iis = detect_html_iis(response, body_text)
        interesting, reasons = classify_candidate(response.status_code, response.headers.get("content-type"), looks_json, keyword_hits)

        return DeepScanProbe(
            base_url=base_url,
            path=path,
            url=url,
            method=method,
            status=response.status_code,
            content_type=response.headers.get("content-type"),
            elapsed_ms=elapsed_ms,
            response_size=len(response.content),
            preview=preview,
            looks_wso2=looks_wso2,
            looks_html_iis=looks_html_iis,
            looks_json=looks_json,
            keyword_hits=keyword_hits,
            interesting=interesting,
            interesting_reasons=reasons,
        )
    except httpx.HTTPError as exc:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return DeepScanProbe(
            base_url=base_url,
            path=path,
            url=url,
            method=method,
            status=None,
            content_type=None,
            elapsed_ms=elapsed_ms,
            response_size=0,
            preview="",
            looks_wso2=False,
            looks_html_iis=False,
            looks_json=False,
            error=f"{exc.__class__.__name__}: {exc}",
        )


def classify_candidate(
    status_code: int,
    content_type: str | None,
    looks_json: bool,
    keyword_hits: list[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if status_code != 404:
        reasons.append("status_different_from_404")
    if status_code in {200, 201, 204}:
        reasons.append("successful_status")
    if status_code in INTERESTING_STATUSES - {200, 201, 204}:
        reasons.append("auth_or_method_signal")
    if looks_json or (content_type and "json" in content_type.lower()):
        reasons.append("json_content")
    if keyword_hits:
        reasons.append(f"keywords:{','.join(keyword_hits)}")

    return bool(reasons), reasons


def detect_keywords(value: str) -> list[str]:
    normalized = normalize_text(value)
    return [keyword for keyword in INTERESTING_KEYWORDS if keyword in normalized]


def detect_wso2(response: httpx.Response, value: str) -> bool:
    combined = normalize_text(value)
    for key, header_value in response.headers.items():
        combined += f" {normalize_text(key)} {normalize_text(header_value)}"

    markers = ("wso2", "api manager", "carbon", "am#")
    return any(marker in combined for marker in markers)


def detect_html_iis(response: httpx.Response, value: str) -> bool:
    combined = normalize_text(value)
    server = normalize_text(response.headers.get("server", ""))
    content_type = normalize_text(response.headers.get("content-type", ""))
    iis_markers = ("microsoft-iis", "internet information services", " iis ", "iis windows")

    if any(marker in server for marker in iis_markers):
        return True
    if "html" in content_type and any(marker in combined for marker in iis_markers):
        return True
    if "html" in content_type and "404 - file or directory not found" in combined:
        return True
    return False


def detect_json(response: httpx.Response, value: str) -> bool:
    content_type = response.headers.get("content-type", "")
    if "json" in content_type.lower():
        return True
    if not value.strip():
        return False
    try:
        json.loads(value)
        return True
    except ValueError:
        return False


def build_summary(report: DeepScanReport, token, probes: list[DeepScanProbe]) -> dict[str, Any]:
    results = [probe.to_summary() for probe in probes]
    candidates = [result for result in results if result["interesting"]]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(report.log_path),
        "summary_path": str(report.summary_path),
        "project_root": str(PROJECT_ROOT),
        "token_url": token.token_url,
        "token_type": token.token_type,
        "access_token_masked": token.masked_access_token,
        "methods": list(METHODS),
        "base_urls": list(BASE_URLS),
        "paths": list(PATHS),
        "total_calls": len(probes),
        "status_counts": count_statuses(probes),
        "interesting_count": len(candidates),
        "wso2_detected": any(probe.looks_wso2 for probe in probes),
        "html_iis_detected": any(probe.looks_html_iis for probe in probes),
        "json_detected": any(probe.looks_json for probe in probes),
        "candidates": candidates,
        "results": results,
    }


def build_failure_summary(report: DeepScanReport, probes: list[DeepScanProbe]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(report.log_path),
        "summary_path": str(report.summary_path),
        "project_root": str(PROJECT_ROOT),
        "total_calls": len(probes),
        "status_counts": count_statuses(probes),
        "interesting_count": 0,
        "wso2_detected": any(probe.looks_wso2 for probe in probes),
        "html_iis_detected": any(probe.looks_html_iis for probe in probes),
        "json_detected": any(probe.looks_json for probe in probes),
        "candidates": [],
        "results": [probe.to_summary() for probe in probes],
    }


def count_statuses(probes: list[DeepScanProbe]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for probe in probes:
        key = str(probe.status) if probe.status is not None else "ERROR"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def format_status_counts(status_counts: dict[str, int]) -> str:
    if not status_counts:
        return "-"
    return ", ".join(f"{status}={count}" for status, count in status_counts.items())


def format_auth_attempt(attempt, secrets: list[str]) -> str:
    status = attempt.status_code if attempt.status_code is not None else "ERROR"
    content_type = attempt.content_type or "-"
    preview = masked_preview(attempt.preview or "", secrets)
    error = f"\n  error={attempt.error}" if attempt.error else ""
    return (
        f"- POST {attempt.token_url} | status={status} | content-type={content_type}\n"
        f"  preview={preview}{error}"
    )


def format_probe(probe: DeepScanProbe) -> str:
    status = probe.status if probe.status is not None else "ERROR"
    preview = probe.preview or probe.error or ""
    return (
        f"- {probe.method} {probe.url} | status={status} | content-type={probe.content_type or '-'} | "
        f"elapsed_ms={probe.elapsed_ms} | size={probe.response_size} | "
        f"wso2={probe.looks_wso2} | html_iis={probe.looks_html_iis} | json={probe.looks_json} | "
        f"keywords={probe.keyword_hits} | interesting={probe.interesting}\n"
        f"  preview={preview}"
    )


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def masked_preview(value: str, secrets: list[str]) -> str:
    redacted = value or ""
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return safe_preview(redacted, limit=500)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return f" {ascii_text.lower()} "


if __name__ == "__main__":
    raise SystemExit(main())
