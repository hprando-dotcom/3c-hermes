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


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    summary_path = logs_dir / f"publication_source_inspection_{timestamp}.json"

    from hermes.connectors.publications.source_inspector import inspect_source

    result = inspect_source(args.url, probe_endpoints=args.probe_endpoints)
    summary = compact_summary(result)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Resumo completo salvo em: {summary_path}")
    return 0 if result.get("ok") else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an official publication source URL.")
    parser.add_argument("--url", required=True, help="URL da fonte oficial.")
    parser.add_argument("--probe-endpoints", action="store_true", help="Testa os primeiros endpoints detectados.")
    return parser.parse_args()


def compact_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": result.get("url"),
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "content_type": result.get("content_type"),
        "title": result.get("title"),
        "links": len(result.get("links", [])),
        "pdf_links": len(result.get("pdf_links", [])),
        "publication_candidates": len(result.get("publication_candidates", [])),
        "endpoint_candidates": len(result.get("endpoint_candidates", [])),
        "error": result.get("error"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
