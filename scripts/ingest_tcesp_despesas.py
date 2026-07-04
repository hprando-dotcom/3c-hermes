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


class ScriptReport:
    def __init__(self, prefix: str) -> None:
        self.logs_dir = PROJECT_ROOT / "logs"
        self.lines: list[str] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"{prefix}_{self.timestamp}.log"
        self.summary_path = self.logs_dir / f"{prefix}_summary_{self.timestamp}.json"

    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line)

    def emit_result(self, result: dict[str, Any]) -> None:
        self.emit(
            f"Resultado: fetched={result.get('fetched')} inserted={result.get('inserted')} "
            f"updated={result.get('updated')} skipped={result.get('skipped')}"
        )
        for error in result.get("errors", []):
            self.emit(f"- erro: {error}")

    def save(self, summary: dict[str, Any]) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Log salvo em: {self.log_path}")
        print(f"Resumo JSON salvo em: {self.summary_path}")


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    report = ScriptReport("tcesp_despesas_ingest")
    summary: dict[str, Any] = {"args": vars(args), "result": None, "errors": []}
    exit_code = 0

    report.emit("HERMES - Ingestao TCE-SP Despesas")
    report.emit(f"Projeto: {PROJECT_ROOT}")
    report.emit(f"Municipio: {args.municipio} | ano={args.ano} | mes={args.mes} | limite={args.limite}")
    report.emit(f"Dry-run: {args.dry_run}")
    report.emit("")

    try:
        from hermes.database.session import engine
        from hermes.services.tcesp_ingestion import ingest_despesas

        if not args.dry_run and not all_tables_exist(engine, ["tcesp_municipios", "tcesp_despesas"]):
            message = "Tabelas TCE-SP nao encontradas. Rode: docker compose run --rm api alembic upgrade head"
            report.emit(message)
            summary["errors"].append(message)
            exit_code = 3
            return exit_code

        result = ingest_despesas(
            args.municipio,
            args.ano,
            args.mes,
            limite=args.limite,
            dry_run=args.dry_run,
        )
        summary["result"] = result
        report.emit_result(result)
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
        report.save(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest TCE-SP despesas into HERMES database.")
    parser.add_argument("--municipio", default="balsamo", help="Slug ou nome do municipio no TCE-SP.")
    parser.add_argument("--ano", type=int, default=2015, help="Exercicio da consulta.")
    parser.add_argument("--mes", type=int, default=1, choices=range(1, 13), help="Mes da consulta.")
    parser.add_argument("--limite", type=int, default=None, help="Limite local de registros apos a busca.")
    parser.add_argument("--dry-run", action="store_true", help="Busca e normaliza sem persistir no banco.")
    return parser.parse_args()


def all_tables_exist(engine, table_names: list[str]) -> bool:
    existing = set(inspect(engine).get_table_names())
    return all(name in existing for name in table_names)


if __name__ == "__main__":
    raise SystemExit(main())
