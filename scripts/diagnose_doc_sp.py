from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hermes.connectors.doc_sp.auth import ApilibAuthError, ApilibAuthenticator, ApilibCredentials, mask_secret
from hermes.connectors.doc_sp.client import DocSpClient


def main() -> int:
    report = DiagnosisReport(PROJECT_ROOT / "logs")
    load_dotenv(PROJECT_ROOT / ".env")

    report.emit("HERMES - Diagnostico DOC SP / APILIB")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Arquivo .env carregado: {(PROJECT_ROOT / '.env').exists()}")
    report.emit("")

    try:
        credentials = ApilibCredentials.from_env()
        report.emit("Credenciais:")
        report.emit(f"- SP_DOE_CONSUMER_KEY: {mask_secret(credentials.consumer_key, visible=6)}")
        report.emit("- SP_DOE_CONSUMER_SECRET: <configured, not printed>")
        report.emit("")

        report.emit("Autenticacao OAuth2 client_credentials:")
        auth_result = ApilibAuthenticator(credentials).request_token()
        for attempt in auth_result.attempts:
            report.emit(format_auth_attempt(attempt))

        token = auth_result.token
        report.emit(f"Token obtido via: {token.token_url}")
        report.emit(f"Token type: {token.token_type}")
        report.emit(f"Access token: {token.masked_access_token}")
        report.emit(f"Expires in: {token.expires_in}")
        report.emit("")

        report.emit("Testes de endpoints:")
        client = DocSpClient(token)
        probes = client.probe()
        for probe in probes:
            report.emit(format_probe(probe))

        ok_count = sum(1 for probe in probes if probe.ok)
        report.emit("")
        report.emit(f"Resumo: {ok_count}/{len(probes)} chamadas retornaram status 2xx.")
        return 0
    except ApilibAuthError as exc:
        report.emit(f"Falha de autenticacao: {exc}")
        for attempt in exc.attempts:
            report.emit(format_auth_attempt(attempt))
        return 2
    except Exception as exc:
        report.emit(f"Falha inesperada: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        path = report.save()
        print(f"Relatorio salvo em: {path}")


class DiagnosisReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.logs_dir / f"doc_sp_diagnosis_{timestamp}.log"

    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line)

    def save(self) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return self.path


def format_auth_attempt(attempt) -> str:
    status = attempt.status_code if attempt.status_code is not None else "ERROR"
    content_type = attempt.content_type or "-"
    preview = attempt.preview or ""
    error = f"\n  error={attempt.error}" if attempt.error else ""
    return (
        f"- POST {attempt.token_url} | status={status} | content-type={content_type}\n"
        f"  preview={preview[:500]}{error}"
    )


def format_probe(probe) -> str:
    params = probe.request.params or {}
    status = probe.status_code if probe.status_code is not None else "ERROR"
    content_type = probe.content_type or "-"
    preview = probe.preview or probe.error or ""
    return (
        f"- GET {probe.request.url} | params={params} | status={status} | "
        f"content-type={content_type} | elapsed_ms={probe.elapsed_ms}\n"
        f"  preview={preview[:500]}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
