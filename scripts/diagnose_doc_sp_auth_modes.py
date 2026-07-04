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

DOC_SP_BASE_URL = "https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1"
DOC_SP_ENDPOINTS = ("/Publicacao", "/Licitacao")
DOC_SP_PARAMS = {"dataPublicacao": "2020-09-01", "caderno": 11}


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
class GrantAttempt:
    mode: str
    token_url: str
    status_code: int | None
    content_type: str | None
    preview: str
    elapsed_ms: float
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
            "preview": self.preview,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


@dataclass(slots=True)
class AuthModeResult:
    mode: str
    token: ApilibToken | None = None
    attempts: list[GrantAttempt] = field(default_factory=list)
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


@dataclass(slots=True)
class EndpointProbe:
    mode: str
    endpoint: str
    url: str
    params: dict[str, Any]
    status_code: int | None
    content_type: str | None
    elapsed_ms: float
    response_size: int
    preview: str
    looks_json: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300

    def to_summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "endpoint": self.endpoint,
            "url": self.url,
            "params": self.params,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "elapsed_ms": self.elapsed_ms,
            "response_size": self.response_size,
            "preview": self.preview,
            "looks_json": self.looks_json,
            "ok": self.ok,
            "error": self.error,
        }


class AuthModesReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"doc_sp_auth_modes_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"doc_sp_auth_modes_summary_{self.timestamp}.json"

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
    report = AuthModesReport(PROJECT_ROOT / "logs")
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    auth_results: list[AuthModeResult] = []
    probes: list[EndpointProbe] = []
    exit_code = 0

    report.emit("HERMES - Diagnostico DOC SP / modos de autenticacao")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Arquivo .env carregado: {env_path.exists()}")
    report.emit(f"Base DOC-SP: {DOC_SP_BASE_URL}")
    report.emit(f"Endpoints: {', '.join(DOC_SP_ENDPOINTS)}")
    report.emit(f"Parametros: {DOC_SP_PARAMS}")
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

        report.emit("Credenciais configuradas:")
        report.emit(f"- SP_DOE_CONSUMER_KEY: {mask_secret(consumer_credentials.consumer_key, visible=6)}")
        report.emit("- SP_DOE_CONSUMER_SECRET: <configured, not printed>")
        report.emit(f"- SP_DOE_USERNAME: {mask_secret(password_credentials.username, visible=3)}")
        report.emit("- SP_DOE_PASSWORD: <configured, not printed>")
        report.emit("")

        auth_results = [
            request_auth_mode("client_credentials", consumer_credentials, password_credentials, secrets, report),
            request_auth_mode("password", consumer_credentials, password_credentials, secrets, report),
        ]

        for auth_result in auth_results:
            if not auth_result.token:
                continue
            secrets.append(auth_result.token.access_token)
            probes.extend(probe_doc_sp_endpoints(auth_result, secrets, report))

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
    report: AuthModesReport,
) -> AuthModeResult:
    result = AuthModeResult(mode=mode)

    report.emit(f"Autenticacao OAuth2 grant_type={mode}:")
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for token_url in build_token_url_candidates():
            attempt, response = request_token_once(client, mode, token_url, consumer_credentials, password_credentials, secrets)
            result.attempts.append(attempt)
            report.emit(format_grant_attempt(attempt))

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
) -> tuple[GrantAttempt, httpx.Response | None]:
    started = perf_counter()
    try:
        response = client.post(
            token_url,
            data=build_token_payload(mode, password_credentials),
            auth=(consumer_credentials.consumer_key, consumer_credentials.consumer_secret),
            headers={"Accept": "application/json"},
        )
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        attempt = GrantAttempt(
            mode=mode,
            token_url=token_url,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            preview=masked_preview(response.text, secrets),
            elapsed_ms=elapsed_ms,
        )
        return attempt, response
    except httpx.HTTPError as exc:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return (
            GrantAttempt(
                mode=mode,
                token_url=token_url,
                status_code=None,
                content_type=None,
                preview="",
                elapsed_ms=elapsed_ms,
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


def probe_doc_sp_endpoints(
    auth_result: AuthModeResult,
    secrets: list[str],
    report: AuthModesReport,
) -> list[EndpointProbe]:
    if auth_result.token is None:
        return []

    report.emit(f"Testes DOC-SP com grant_type={auth_result.mode}:")
    probes: list[EndpointProbe] = []
    headers = {
        "Authorization": auth_result.token.authorization_header,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for endpoint in DOC_SP_ENDPOINTS:
            probe = execute_endpoint_probe(client, auth_result.mode, endpoint, headers, secrets)
            probes.append(probe)
            report.emit(format_endpoint_probe(probe))

    report.emit("")
    return probes


def execute_endpoint_probe(
    client: httpx.Client,
    mode: str,
    endpoint: str,
    headers: dict[str, str],
    secrets: list[str],
) -> EndpointProbe:
    url = build_url(DOC_SP_BASE_URL, endpoint)
    started = perf_counter()

    try:
        response = client.get(url, params=DOC_SP_PARAMS, headers=headers)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        body = response.text if response.content else ""
        return EndpointProbe(
            mode=mode,
            endpoint=endpoint,
            url=str(response.url),
            params=dict(DOC_SP_PARAMS),
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            elapsed_ms=elapsed_ms,
            response_size=len(response.content),
            preview=masked_preview(body, secrets),
            looks_json=looks_json(response, body),
        )
    except httpx.HTTPError as exc:
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        return EndpointProbe(
            mode=mode,
            endpoint=endpoint,
            url=url,
            params=dict(DOC_SP_PARAMS),
            status_code=None,
            content_type=None,
            elapsed_ms=elapsed_ms,
            response_size=0,
            preview="",
            looks_json=False,
            error=f"{exc.__class__.__name__}: {exc}",
        )


def build_summary(
    report: AuthModesReport,
    auth_results: list[AuthModeResult],
    probes: list[EndpointProbe],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(report.log_path),
        "summary_path": str(report.summary_path),
        "project_root": str(PROJECT_ROOT),
        "base_url": DOC_SP_BASE_URL,
        "endpoints": list(DOC_SP_ENDPOINTS),
        "params": DOC_SP_PARAMS,
        "auth_modes": {result.mode: result.to_summary() for result in auth_results},
        "probes": [probe.to_summary() for probe in probes],
        "comparison": build_comparison(probes),
    }


def build_comparison(probes: list[EndpointProbe]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for endpoint in DOC_SP_ENDPOINTS:
        endpoint_probes = [probe for probe in probes if probe.endpoint == endpoint]
        by_mode = {probe.mode: probe.status_code for probe in endpoint_probes}
        client_status = by_mode.get("client_credentials")
        password_status = by_mode.get("password")
        comparison[endpoint] = {
            "statuses_by_mode": by_mode,
            "client_credentials_status": client_status,
            "password_status": password_status,
            "status_changed": (
                client_status is not None
                and password_status is not None
                and client_status != password_status
            ),
            "any_2xx": any(probe.ok for probe in endpoint_probes),
        }
    return comparison


def emit_final_summary(report: AuthModesReport, summary: dict[str, Any]) -> None:
    report.emit("Resumo final:")
    for mode, auth_summary in summary["auth_modes"].items():
        report.emit(f"- grant_type={mode}: token={'sim' if auth_summary['ok'] else 'nao'}")
    for endpoint, comparison in summary["comparison"].items():
        report.emit(
            f"- {endpoint}: client_credentials={comparison['client_credentials_status']} | "
            f"password={comparison['password_status']} | mudou={comparison['status_changed']} | "
            f"algum_2xx={comparison['any_2xx']}"
        )


def format_grant_attempt(attempt: GrantAttempt) -> str:
    status = attempt.status_code if attempt.status_code is not None else "ERROR"
    content_type = attempt.content_type or "-"
    error = f"\n  error={attempt.error}" if attempt.error else ""
    return (
        f"- POST {attempt.token_url} | status={status} | content-type={content_type} | "
        f"elapsed_ms={attempt.elapsed_ms}\n"
        f"  preview={attempt.preview}{error}"
    )


def format_endpoint_probe(probe: EndpointProbe) -> str:
    status = probe.status_code if probe.status_code is not None else "ERROR"
    preview = probe.preview or probe.error or ""
    return (
        f"- GET {probe.url} | grant_type={probe.mode} | params={probe.params} | status={status} | "
        f"content-type={probe.content_type or '-'} | elapsed_ms={probe.elapsed_ms} | "
        f"size={probe.response_size} | json={probe.looks_json}\n"
        f"  preview={preview}"
    )


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def looks_json(response: httpx.Response, body: str) -> bool:
    content_type = response.headers.get("content-type", "")
    if "json" in content_type.lower():
        return True
    if not body.strip():
        return False
    try:
        json.loads(body)
        return True
    except ValueError:
        return False


def masked_preview(value: str, secrets: list[str]) -> str:
    redacted = value or ""
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return safe_preview(redacted, limit=500)


if __name__ == "__main__":
    raise SystemExit(main())
