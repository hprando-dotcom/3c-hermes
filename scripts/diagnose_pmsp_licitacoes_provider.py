from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hermes.connectors.doc_sp.auth import ApilibAuthError, ApilibAuthenticator, ApilibCredentials, mask_secret
from hermes.connectors.pmsp.licitacoes.provider import PmspLicitacoesProvider, PmspLicitacoesProviderResult

YEARS_TO_TEST = (2005, 2010, 2015, 2019)
DEFAULT_LIMITE = 100
DEFAULT_OFFSET = 0


class ProviderDiagnosisReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"pmsp_licitacoes_provider_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"pmsp_licitacoes_provider_summary_{self.timestamp}.json"

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
    report = ProviderDiagnosisReport(PROJECT_ROOT / "logs")
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    auth_summary: dict[str, Any] = {"ok": False, "attempts": []}
    results: list[PmspLicitacoesProviderResult] = []
    exit_code = 0

    report.emit("HERMES - Diagnostico PMSP Licitacoes Provider")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Arquivo .env carregado: {env_path.exists()}")
    report.emit(f"Anos testados: {', '.join(str(year) for year in YEARS_TO_TEST)}")
    report.emit(f"Query padrao: limite={DEFAULT_LIMITE}, offset={DEFAULT_OFFSET}")
    report.emit("")

    try:
        token = None
        try:
            credentials = ApilibCredentials.from_env()
            report.emit("Credenciais APILIB:")
            report.emit(f"- SP_DOE_CONSUMER_KEY: {mask_secret(credentials.consumer_key, visible=6)}")
            report.emit("- SP_DOE_CONSUMER_SECRET: <configured, not printed>")
            report.emit("")

            auth_result = ApilibAuthenticator(credentials).request_token()
            token = auth_result.token
            auth_summary = {
                "ok": True,
                "token_url": token.token_url,
                "token_type": token.token_type,
                "expires_in": token.expires_in,
                "access_token_masked": token.masked_access_token,
                "attempts": [format_auth_attempt_summary(attempt) for attempt in auth_result.attempts],
            }
            report.emit("Autenticacao APILIB client_credentials: ok")
            report.emit(f"- Token: {token.masked_access_token}")
            report.emit("")
        except ApilibAuthError as exc:
            auth_summary = {
                "ok": False,
                "error": str(exc),
                "attempts": [format_auth_attempt_summary(attempt) for attempt in exc.attempts],
            }
            report.emit(f"Autenticacao APILIB client_credentials falhou: {exc}")
            report.emit("Provider seguira com fallback CKAN quando possivel.")
            report.emit("")

        provider = PmspLicitacoesProvider(token=token)
        for ano in YEARS_TO_TEST:
            result = provider.list_by_year(ano, limite=DEFAULT_LIMITE, offset=DEFAULT_OFFSET)
            results.append(result)
            report.emit(format_provider_result(result))

        summary = build_summary(report, auth_summary, results)
        emit_final_summary(report, summary)
        if not any(result.ok for result in results):
            exit_code = 2
        return exit_code
    except Exception as exc:
        report.emit(f"Falha inesperada: {exc.__class__.__name__}: {exc}")
        exit_code = 1
        return exit_code
    finally:
        summary = build_summary(report, auth_summary, results)
        summary["exit_code"] = exit_code
        summary_path = report.save_summary(summary)
        log_path = report.save_log()
        print(f"Relatorio salvo em: {log_path}")
        print(f"Resumo JSON salvo em: {summary_path}")


def build_summary(
    report: ProviderDiagnosisReport,
    auth_summary: dict[str, Any],
    results: list[PmspLicitacoesProviderResult],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(report.log_path),
        "summary_path": str(report.summary_path),
        "project_root": str(PROJECT_ROOT),
        "years": list(YEARS_TO_TEST),
        "default_query": {"limite": DEFAULT_LIMITE, "offset": DEFAULT_OFFSET},
        "apilib_auth": auth_summary,
        "results": [result.to_summary(include_records=False) for result in results],
    }


def format_provider_result(result: PmspLicitacoesProviderResult) -> str:
    errors = [error.to_summary() for error in result.errors]
    return (
        f"- ano={result.ano} | fonte={result.source_used or '-'} | status={result.status_code} | "
        f"total={result.total} | retornados={result.record_count} | ok={result.ok} | erros={errors}"
    )


def emit_final_summary(report: ProviderDiagnosisReport, summary: dict[str, Any]) -> None:
    report.emit("")
    report.emit("Resumo final:")
    report.emit(f"- APILIB auth: {'ok' if summary['apilib_auth'].get('ok') else 'falhou'}")
    for result in summary["results"]:
        report.emit(
            f"- ano={result['ano']}: fonte={result['source_used'] or '-'} | "
            f"status={result['status_code']} | total={result['total']} | "
            f"retornados={result['record_count']} | ok={result['ok']}"
        )


def format_auth_attempt_summary(attempt) -> dict[str, Any]:
    return {
        "token_url": attempt.token_url,
        "status_code": attempt.status_code,
        "content_type": attempt.content_type,
        "preview": attempt.preview,
        "error": attempt.error,
    }


if __name__ == "__main__":
    raise SystemExit(main())
