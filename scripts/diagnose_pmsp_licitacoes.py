from __future__ import annotations

import json
import os
import sys
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

from hermes.connectors.doc_sp.auth import (
    ApilibAuthError,
    ApilibCredentials,
    ApilibToken,
    build_token_url_candidates,
    mask_secret,
    parse_token_response,
    safe_preview,
)
from hermes.connectors.pmsP_licitacoes.client import (
    PMSP_LICITACOES_BASE_URL,
    PmspLicitacoesClient,
    PmspLicitacoesResponse,
)

AUTH_MODES = ("client_credentials", "password")
YEARS_TO_TEST = (2005, 2010, 2015, 2019)
DEFAULT_LIMITE = 10
DEFAULT_OFFSET = 0


@dataclass(slots=True)
class PasswordGrantCredentials:
    username: str
    password: str

    @classmethod
    def from_env(cls) -> PasswordGrantCredentials:
        username = os.getenv("SP_DOE_USERNAME")
        password = os.getenv("SP_DOE_PASSWORD")
        missing = [
            name
            for name, value in (
                ("SP_DOE_USERNAME", username),
                ("SP_DOE_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            raise ApilibAuthError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(username=username or "", password=password or "")


@dataclass(slots=True)
class TokenAttempt:
    mode: str
    token_url: str
    status_code: int | None
    content_type: str | None
    elapsed_ms: float
    preview: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    def to_summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "token_url": self.token_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "elapsed_ms": self.elapsed_ms,
            "preview": self.preview,
            "error": self.error,
        }


@dataclass(slots=True)
class AuthModeResult:
    mode: str
    token: ApilibToken | None = None
    attempts: list[TokenAttempt] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.token is not None

    def to_summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "token_url": self.token.token_url if self.token else None,
            "token_type": self.token.token_type if self.token else None,
            "expires_in": self.token.expires_in if self.token else None,
            "scope": self.token.scope if self.token else None,
            "access_token_masked": self.token.masked_access_token if self.token else None,
            "attempts": [attempt.to_summary() for attempt in self.attempts],
            "error": self.error,
        }


class PmspLicitacoesReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"pmsp_licitacoes_diagnosis_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"pmsp_licitacoes_diagnosis_summary_{self.timestamp}.json"

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
    report = PmspLicitacoesReport(PROJECT_ROOT / "logs")
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    auth_results: list[AuthModeResult] = []
    probes: list[dict[str, Any]] = []
    exit_code = 0

    report.emit("HERMES - Diagnostico PMSP Licitacoes / APILIB")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Arquivo .env carregado: {env_path.exists()}")
    report.emit(f"Base: {PMSP_LICITACOES_BASE_URL}")
    report.emit(f"Endpoint: GET /{{ano}}")
    report.emit(f"Anos testados: {', '.join(str(year) for year in YEARS_TO_TEST)}")
    report.emit(f"Query padrao: limite={DEFAULT_LIMITE}, offset={DEFAULT_OFFSET}")
    report.emit("")

    try:
        consumer_credentials = ApilibCredentials.from_env()
        password_credentials = PasswordGrantCredentials.from_env()
        secrets = [
            consumer_credentials.consumer_key,
            consumer_credentials.consumer_secret,
            password_credentials.username,
            password_credentials.password,
        ]

        report.emit("Credenciais APILIB configuradas:")
        report.emit(f"- SP_DOE_CONSUMER_KEY: {mask_secret(consumer_credentials.consumer_key, visible=6)}")
        report.emit("- SP_DOE_CONSUMER_SECRET: <configured, not printed>")
        report.emit(f"- SP_DOE_USERNAME: {mask_secret(password_credentials.username, visible=3)}")
        report.emit("- SP_DOE_PASSWORD: <configured, not printed>")
        report.emit("")

        for mode in AUTH_MODES:
            auth_result = request_auth_mode(mode, consumer_credentials, password_credentials, secrets, report)
            auth_results.append(auth_result)
            if auth_result.token:
                secrets.append(auth_result.token.access_token)
                probes.extend(run_licitacoes_probes(auth_result, secrets, report))

        summary = build_summary(report, auth_results, probes)
        emit_final_summary(report, summary)

        if not any(result.ok for result in auth_results):
            exit_code = 2
        return exit_code
    except ApilibAuthError as exc:
        report.emit(f"Falha de configuracao/autenticacao: {exc}")
        exit_code = 2
        return exit_code
    except Exception as exc:
        report.emit(f"Falha inesperada: {exc.__class__.__name__}: {exc}")
        exit_code = 1
        return exit_code
    finally:
        summary = build_summary(report, auth_results, probes)
        summary["exit_code"] = exit_code
        summary_path = report.save_summary(summary)
        log_path = report.save_log()
        print(f"Relatorio salvo em: {log_path}")
        print(f"Resumo JSON salvo em: {summary_path}")


def request_auth_mode(
    mode: str,
    consumer_credentials: ApilibCredentials,
    password_credentials: PasswordGrantCredentials,
    secrets: list[str],
    report: PmspLicitacoesReport,
) -> AuthModeResult:
    result = AuthModeResult(mode=mode)

    report.emit(f"Autenticacao OAuth2 grant_type={mode}:")
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for token_url in build_token_url_candidates():
            attempt, response = request_token_once(client, mode, token_url, consumer_credentials, password_credentials, secrets)
            result.attempts.append(attempt)
            report.emit(format_token_attempt(attempt))

            if not attempt.ok or response is None:
                continue

            try:
                result.token = parse_token_response(response, token_url)
                report.emit(f"Token {mode}: {result.token.masked_access_token}")
                report.emit("")
                return result
            except ApilibAuthError as exc:
                attempt.error = str(exc)
                result.error = str(exc)

    if result.error is None:
        result.error = f"Unable to obtain APILIB token with grant_type={mode}."
    report.emit(f"Resultado grant_type={mode}: {result.error}")
    report.emit("")
    return result


def request_token_once(
    client: httpx.Client,
    mode: str,
    token_url: str,
    consumer_credentials: ApilibCredentials,
    password_credentials: PasswordGrantCredentials,
    secrets: list[str],
) -> tuple[TokenAttempt, httpx.Response | None]:
    started = perf_counter()

    try:
        response = client.post(
            token_url,
            data=build_token_payload(mode, password_credentials),
            auth=(consumer_credentials.consumer_key, consumer_credentials.consumer_secret),
            headers={"Accept": "application/json"},
        )
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        attempt = TokenAttempt(
            mode=mode,
            token_url=token_url,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            elapsed_ms=elapsed_ms,
            preview=masked_preview(response.text, secrets),
        )
        return attempt, response
    except httpx.HTTPError as exc:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return (
            TokenAttempt(
                mode=mode,
                token_url=token_url,
                status_code=None,
                content_type=None,
                elapsed_ms=elapsed_ms,
                preview="",
                error=f"{exc.__class__.__name__}: {exc}",
            ),
            None,
        )


def build_token_payload(mode: str, password_credentials: PasswordGrantCredentials) -> dict[str, str]:
    if mode == "client_credentials":
        return {"grant_type": "client_credentials"}
    if mode == "password":
        return {
            "grant_type": "password",
            "username": password_credentials.username,
            "password": password_credentials.password,
        }
    raise ValueError(f"Unsupported auth mode: {mode}")


def run_licitacoes_probes(
    auth_result: AuthModeResult,
    secrets: list[str],
    report: PmspLicitacoesReport,
) -> list[dict[str, Any]]:
    if auth_result.token is None:
        return []

    report.emit(f"Testes PMSP Licitacoes com grant_type={auth_result.mode}:")
    client = PmspLicitacoesClient(auth_result.token)
    results: list[dict[str, Any]] = []

    for ano in YEARS_TO_TEST:
        response = client.list_by_year(ano, limite=DEFAULT_LIMITE, offset=DEFAULT_OFFSET)
        probe_summary = response_to_summary(auth_result.mode, response, secrets)
        results.append(probe_summary)
        report.emit(format_probe(auth_result.mode, response, secrets))

    report.emit("")
    return results


def response_to_summary(
    mode: str,
    response: PmspLicitacoesResponse,
    secrets: list[str],
) -> dict[str, Any]:
    return {
        "mode": mode,
        "ano": response.request.ano,
        "url": response.request.url,
        "params": response.request.params,
        "status_code": response.status_code,
        "content_type": response.content_type,
        "elapsed_ms": response.elapsed_ms,
        "response_size": response.response_size,
        "preview": masked_preview(response.preview, secrets),
        "looks_json": response.looks_json,
        "record_count": response.record_count,
        "ok": response.ok,
        "error": response.error,
    }


def build_summary(
    report: PmspLicitacoesReport,
    auth_results: list[AuthModeResult],
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(report.log_path),
        "summary_path": str(report.summary_path),
        "project_root": str(PROJECT_ROOT),
        "base_url": PMSP_LICITACOES_BASE_URL,
        "endpoint": "/{ano}",
        "years": list(YEARS_TO_TEST),
        "default_query": {"limite": DEFAULT_LIMITE, "offset": DEFAULT_OFFSET},
        "auth_modes": {result.mode: result.to_summary() for result in auth_results},
        "probes": probes,
        "comparison": build_comparison(probes),
    }


def build_comparison(probes: list[dict[str, Any]]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for ano in YEARS_TO_TEST:
        year_probes = [probe for probe in probes if probe["ano"] == ano]
        statuses_by_mode = {probe["mode"]: probe["status_code"] for probe in year_probes}
        records_by_mode = {probe["mode"]: probe["record_count"] for probe in year_probes}
        json_by_mode = {probe["mode"]: probe["looks_json"] for probe in year_probes}
        comparison[str(ano)] = {
            "statuses_by_mode": statuses_by_mode,
            "records_by_mode": records_by_mode,
            "json_by_mode": json_by_mode,
            "any_2xx": any(probe["ok"] for probe in year_probes),
        }
    return comparison


def emit_final_summary(report: PmspLicitacoesReport, summary: dict[str, Any]) -> None:
    report.emit("Resumo final:")
    for mode, auth_summary in summary["auth_modes"].items():
        report.emit(f"- grant_type={mode}: token={'sim' if auth_summary['ok'] else 'nao'}")
    for ano, comparison in summary["comparison"].items():
        report.emit(
            f"- ano={ano}: status={comparison['statuses_by_mode']} | "
            f"json={comparison['json_by_mode']} | registros={comparison['records_by_mode']} | "
            f"algum_2xx={comparison['any_2xx']}"
        )


def format_token_attempt(attempt: TokenAttempt) -> str:
    status = attempt.status_code if attempt.status_code is not None else "ERROR"
    content_type = attempt.content_type or "-"
    error = f"\n  error={attempt.error}" if attempt.error else ""
    return (
        f"- POST {attempt.token_url} | status={status} | content-type={content_type} | "
        f"elapsed_ms={attempt.elapsed_ms}\n"
        f"  preview={attempt.preview}{error}"
    )


def format_probe(mode: str, response: PmspLicitacoesResponse, secrets: list[str]) -> str:
    status = response.status_code if response.status_code is not None else "ERROR"
    preview = masked_preview(response.preview or response.error or "", secrets)
    return (
        f"- GET {response.request.url} | grant_type={mode} | params={response.request.params} | "
        f"status={status} | content-type={response.content_type or '-'} | "
        f"elapsed_ms={response.elapsed_ms} | size={response.response_size} | "
        f"json={response.looks_json} | registros={response.record_count}\n"
        f"  preview={preview[:500]}"
    )


def masked_preview(value: str, secrets: list[str]) -> str:
    redacted = value or ""
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return safe_preview(redacted, limit=500)


if __name__ == "__main__":
    raise SystemExit(main())
