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

    from hermes.database.models import PublicSource, Publication, Source
    from hermes.database.session import SessionLocal, engine

    required = {"public_sources", "publications", "sources"}
    missing = sorted(required - set(inspect(engine).get_table_names()))
    if missing:
        print(f"Tabelas ausentes: {', '.join(missing)}")
        print("Rode: docker compose run --rm api alembic upgrade head")
        return 3

    with SessionLocal() as session:
        print("HERMES - Check publicacoes oficiais")
        print("")
        print(f"Fontes publicas: {session.scalar(select(func.count()).select_from(PublicSource)) or 0}")
        print(f"Publicacoes: {session.scalar(select(func.count()).select_from(Publication)) or 0}")
        print("")

        print("Top fontes por publicacoes:")
        rows = session.execute(
            select(Source.name, func.count(Publication.id).label("total"))
            .join(Publication, Publication.source_id == Source.id)
            .group_by(Source.name)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for name, total in rows:
            print(f"- {name}: {total}")
        print("")

        print("Tipos de publicacao:")
        rows = session.execute(
            select(Publication.publication_type, func.count().label("total"))
            .group_by(Publication.publication_type)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for publication_type, total in rows:
            print(f"- {publication_type or '<sem tipo>'}: {total}")
        print("")

        print("Ultimas 10 publicacoes:")
        latest = session.scalars(select(Publication).order_by(desc(Publication.created_at)).limit(10))
        for item in latest:
            print(
                f"- id={item.id} type={item.publication_type or '-'} "
                f"source={item.source_name or '-'} title={(item.object_description or '-')[:120]}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
