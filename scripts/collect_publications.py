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


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    summary_path = logs_dir / f"publications_collect_summary_{timestamp}.json"

    from hermes.database.session import engine
    from hermes.services.publication_collection import collect_publications_from_source

    if not args.dry_run and not tables_exist(engine, ["public_sources", "publications", "sources"]):
        print("Tabelas de publicacoes ausentes. Rode: docker compose run --rm api alembic upgrade head")
        return 3

    result = collect_publications_from_source(
        args.url,
        limit=args.limite,
        dry_run=args.dry_run,
        probe_endpoints=args.probe_endpoints,
    )
    print_result(result)
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Resumo JSON salvo em: {summary_path}")
    return 1 if result.get("errors") else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect official publications from a source URL.")
    parser.add_argument("--url", required=True, help="URL da fonte oficial.")
    parser.add_argument("--limite", type=int, default=100, help="Limite de publicacoes candidatas.")
    parser.add_argument("--dry-run", action="store_true", help="Inspeciona e normaliza sem persistir.")
    parser.add_argument("--probe-endpoints", action="store_true", help="Testa endpoints candidatos.")
    return parser.parse_args()


def tables_exist(engine, names: list[str]) -> bool:
    existing = set(inspect(engine).get_table_names())
    return all(name in existing for name in names)


def print_result(result: dict[str, Any]) -> None:
    print("HERMES - Coleta de publicacoes oficiais")
    print(f"URL: {result.get('url')}")
    print(
        f"fetched={result.get('fetched')} inserted={result.get('inserted')} "
        f"updated={result.get('updated')} skipped={result.get('skipped')}"
    )
    for error in result.get("errors", []):
        print(f"- erro: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
