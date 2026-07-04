from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hermes.connectors.pmsp.licitacoes.dados_abertos import (
    CKAN_SOURCE,
    CKAN_SOURCE_SYSTEM,
    DadosAbertosLicitacoesClient,
    extract_records,
    select_resource_for_year,
)
from hermes.connectors.pmsp.licitacoes.normalizer import detect_record_format, normalize_record, parse_record


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    client = DadosAbertosLicitacoesClient(timeout_seconds=args.timeout)

    if args.resource_id:
        resource_id = args.resource_id
        selected_resource = None
    else:
        resources = client.discover_resources()
        selected_resource = select_resource_for_year(resources, args.ano)
        if selected_resource is None:
            print(f"Nenhum resource CKAN encontrado para ano={args.ano}.")
            return 2
        resource_id = selected_resource.resource_id

    response = client.datastore_search(resource_id, limit=args.limite, offset=args.offset)
    raw_records = extract_records(response.payload)
    original_record = raw_records[0] if raw_records else {}
    detected_type = detect_record_format(original_record) if original_record else "empty"
    parsed_record = parse_record(original_record) if original_record else {}
    normalized_record = (
        normalize_record(original_record, ano=args.ano, source=CKAN_SOURCE, source_system=CKAN_SOURCE_SYSTEM)
        if original_record
        else {}
    )

    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ano": args.ano,
        "resource_id": resource_id,
        "selected_resource": selected_resource.to_summary() if selected_resource else None,
        "request": response.to_summary(),
        "raw_payload": response.payload,
        "detected_type": detected_type,
        "original_record": original_record,
        "parsed_record": parsed_record,
        "normalized_record": normalized_record,
    }

    print_section("payload bruto", response.payload)
    print_section("tipo detectado", detected_type)
    print_section("registro original", original_record)
    print_section("registro parseado", parsed_record)
    print_section("registro normalizado", normalized_record)

    path = save_snapshot(snapshot)
    print(f"\nSnapshot salvo em: {path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug one PMSP Licitacoes CKAN record.")
    parser.add_argument("--ano", type=int, default=2015)
    parser.add_argument("--resource-id", help="Resource ID CKAN especifico.")
    parser.add_argument("--limite", type=int, default=3)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def print_section(title: str, value: Any) -> None:
    print(f"\n## {title}")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def save_snapshot(snapshot: dict[str, Any]) -> Path:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = logs_dir / f"pmsp_record_debug_{timestamp}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
