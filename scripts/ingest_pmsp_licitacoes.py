from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class IngestReport:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"pmsp_licitacoes_ingest_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"pmsp_licitacoes_ingest_summary_{self.timestamp}.json"

    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line)

    def save_log(self) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return self.log_path

    def save_summary(self, summary: dict[str, Any]) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        return self.summary_path


def main() -> int:
    args = parse_args()
    report = IngestReport(PROJECT_ROOT / "logs")
    load_dotenv(PROJECT_ROOT / ".env")

    summary: dict[str, Any] = {
        "args": vars(args),
        "result": None,
        "errors": [],
    }
    exit_code = 0

    report.emit("HERMES - Ingestao PMSP Licitacoes")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Dry-run: {args.dry_run}")
    report.emit("")

    try:
        from hermes.database.session import engine
        from hermes.services.pmsp_licitacoes_ingestion import ingest_year, ingest_year_range

        if not args.dry_run and not table_exists(engine, "pmsp_licitacoes"):
            message = "Tabela pmsp_licitacoes nao encontrada. Rode: docker compose run --rm api alembic upgrade head"
            report.emit(message)
            summary["errors"].append(message)
            exit_code = 3
            return exit_code

        if args.ano is not None:
            result = ingest_year(
                args.ano,
                limite=args.limite,
                offset=args.offset,
                dry_run=args.dry_run,
            )
        else:
            result = ingest_year_range(
                args.inicio,
                args.fim,
                limite=args.limite,
                offset=args.offset,
                dry_run=args.dry_run,
            )

        summary["result"] = result
        emit_result(report, result)
        if result.get("errors"):
            exit_code = 1
        return exit_code
    except Exception as exc:
        message = f"Falha inesperada: {exc.__class__.__name__}: {exc}"
        report.emit(message)
        summary["errors"].append(message)
        exit_code = 1
        return exit_code
    finally:
        summary["exit_code"] = exit_code
        summary_path = report.save_summary(summary)
        log_path = report.save_log()
        print(f"Relatorio salvo em: {log_path}")
        print(f"Resumo JSON salvo em: {summary_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest PMSP Licitacoes into HERMES database.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--ano", type=int, help="Ano unico para ingestao.")
    target.add_argument("--inicio", type=int, help="Ano inicial para ingestao em faixa.")
    parser.add_argument("--fim", type=int, help="Ano final para ingestao em faixa.")
    parser.add_argument("--limite", type=int, default=100, help="Limite de registros por chamada.")
    parser.add_argument("--offset", type=int, default=0, help="Offset inicial.")
    parser.add_argument("--dry-run", action="store_true", help="Busca e normaliza sem persistir no banco.")
    args = parser.parse_args()

    if args.inicio is not None and args.fim is None:
        parser.error("--fim e obrigatorio quando --inicio for usado.")
    if args.fim is not None and args.inicio is None:
        parser.error("--inicio e obrigatorio quando --fim for usado.")
    if args.inicio is not None and args.inicio > args.fim:
        parser.error("--inicio deve ser menor ou igual a --fim.")
    return args


def table_exists(engine, table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def emit_result(report: IngestReport, result: dict[str, Any]) -> None:
    if "years" in result:
        report.emit(
            f"Resumo faixa {result['start_year']}-{result['end_year']}: "
            f"fetched={result['fetched']} inserted={result['inserted']} "
            f"updated={result['updated']} skipped={result['skipped']}"
        )
        for year in result["years"]:
            emit_result(report, year)
        return

    report.emit(
        f"Ano {result['ano']}: fetched={result['fetched']} inserted={result['inserted']} "
        f"updated={result['updated']} skipped={result['skipped']} source={result.get('source_used')}"
    )
    for error in result.get("errors", []):
        report.emit(f"- erro: {error}")
    for diagnostic in result.get("diagnostics", []):
        report.emit(
            "- diag: "
            f"resource_id={diagnostic.get('resource_id')} "
            f"resource_name={diagnostic.get('resource_name')} "
            f"tipo={diagnostic.get('tipo_detectado')} "
            f"embedded_csv_field={diagnostic.get('embedded_csv_field')} "
            f"raw_keys={diagnostic.get('raw_keys')} "
            f"parsed_keys={diagnostic.get('parsed_keys')} "
            f"orgao={diagnostic.get('normalized', {}).get('orgao')} "
            f"modalidade={diagnostic.get('normalized', {}).get('modalidade')} "
            f"numero_processo={diagnostic.get('normalized', {}).get('numero_processo')} "
            f"decisao={diagnostic.get('decision')}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
