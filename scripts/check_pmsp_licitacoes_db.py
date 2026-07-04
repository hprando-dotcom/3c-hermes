from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import desc, func, inspect, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    from hermes.database.models import PmspLicitacao
    from hermes.database.session import SessionLocal, engine

    if "pmsp_licitacoes" not in inspect(engine).get_table_names():
        print("Tabela pmsp_licitacoes nao encontrada. Rode: docker compose run --rm api alembic upgrade head")
        return 3

    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(PmspLicitacao)) or 0
        print(f"Total de registros: {total}")
        print("")

        print("Total por ano:")
        rows = session.execute(
            select(PmspLicitacao.ano, func.count())
            .group_by(PmspLicitacao.ano)
            .order_by(PmspLicitacao.ano)
        ).all()
        for ano, count in rows:
            print(f"- {ano}: {count}")
        print("")

        print("Ultimos 10 registros:")
        latest = session.execute(
            select(PmspLicitacao)
            .order_by(desc(PmspLicitacao.created_at))
            .limit(10)
        ).scalars()
        for item in latest:
            print(
                f"- id={item.id} ano={item.ano} orgao={item.orgao or '-'} "
                f"processo={item.numero_processo or '-'} contrato={item.numero_contrato or '-'} "
                f"source={item.source}"
            )
        print("")

        print("Top 10 orgaos:")
        top_organs = session.execute(
            select(PmspLicitacao.orgao, func.count())
            .group_by(PmspLicitacao.orgao)
            .order_by(desc(func.count()))
            .limit(10)
        ).all()
        for orgao, count in top_organs:
            print(f"- {orgao or '<sem orgao>'}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
