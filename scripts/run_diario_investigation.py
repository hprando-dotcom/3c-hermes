from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    from hermes.services.official_gazette_investigation import run_official_gazette_investigation

    report = run_official_gazette_investigation(
        args.url,
        args.mission,
        args.date_start,
        args.date_end,
        limit=args.limit,
        report_dir=PROJECT_ROOT / "data" / "reports",
    )

    print("HERMES - Investigacao de Diario Oficial")
    print(f"Fonte: {report.source_url}")
    print(f"Periodo: {report.date_start or 'nao informado'} a {report.date_end or 'nao informado'}")
    print(f"Documentos analisados: {report.documents_analyzed}")
    print(f"Links encontrados: {report.links_found}")
    print(f"Achados relevantes: {len(report.findings)}")
    print(f"Inteligencia: {'DeepSeek' if report.used_deepseek else 'fallback deterministico'}")
    print(f"ID da investigacao: {report.investigation_id}")
    print(f"Relatorio Markdown: {report.markdown_path}")
    print(f"Relatorio HTML: {report.report_html_path}")
    print(f"CSV de achados: {report.csv_path}")
    print(f"JSON estruturado: {report.json_path}")
    print(f"Dossie ZIP: {report.zip_path}")
    if report.limitations:
        print("")
        print("Limitacoes:")
        for limitation in report.limitations:
            print(f"- {limitation}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HERMES official gazette investigation.")
    parser.add_argument("--url", required=True, help="URL do Diario Oficial ou portal publico.")
    parser.add_argument("--mission", required=True, help="Missao em linguagem natural.")
    parser.add_argument("--date-start", default=None, help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--date-end", default=None, help="Data final YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=50, help="Maximo de documentos analisados.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
