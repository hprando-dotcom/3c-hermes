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

    from hermes.database.models import TceSpDespesa, TceSpMunicipio, TceSpReceita
    from hermes.database.session import SessionLocal, engine

    required_tables = {"tcesp_municipios", "tcesp_despesas", "tcesp_receitas"}
    existing_tables = set(inspect(engine).get_table_names())
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        print(f"Tabelas TCE-SP ausentes: {', '.join(missing_tables)}")
        print("Rode: docker compose run --rm api alembic upgrade head")
        return 3

    with SessionLocal() as session:
        print("HERMES - Check TCE-SP")
        print("")
        print(f"Municipios: {session.scalar(select(func.count()).select_from(TceSpMunicipio)) or 0}")
        print(f"Despesas: {session.scalar(select(func.count()).select_from(TceSpDespesa)) or 0}")
        print(f"Receitas: {session.scalar(select(func.count()).select_from(TceSpReceita)) or 0}")
        print("")

        print("Campos nulos principais:")
        despesas_sem_fornecedor = session.scalar(
            select(func.count()).select_from(TceSpDespesa).where(TceSpDespesa.nm_fornecedor.is_(None))
        ) or 0
        despesas_sem_valor = session.scalar(
            select(func.count()).select_from(TceSpDespesa).where(TceSpDespesa.vl_despesa.is_(None))
        ) or 0
        receitas_sem_valor = session.scalar(
            select(func.count()).select_from(TceSpReceita).where(TceSpReceita.vl_arrecadacao.is_(None))
        ) or 0
        print(f"- despesas sem fornecedor: {despesas_sem_fornecedor}")
        print(f"- despesas sem valor: {despesas_sem_valor}")
        print(f"- receitas sem valor: {receitas_sem_valor}")
        print("")

        print("Despesas por municipio/exercicio (top 10):")
        rows = session.execute(
            select(TceSpDespesa.municipio_slug, TceSpDespesa.exercicio, func.count().label("total"))
            .group_by(TceSpDespesa.municipio_slug, TceSpDespesa.exercicio)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for municipio, ano, total in rows:
            print(f"- {municipio} {ano}: {total}")
        print("")

        print("Receitas por municipio/exercicio (top 10):")
        rows = session.execute(
            select(TceSpReceita.municipio_slug, TceSpReceita.exercicio, func.count().label("total"))
            .group_by(TceSpReceita.municipio_slug, TceSpReceita.exercicio)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for municipio, ano, total in rows:
            print(f"- {municipio} {ano}: {total}")
        print("")

        print("Top 10 fornecedores por valor de despesas:")
        rows = session.execute(
            select(TceSpDespesa.nm_fornecedor, func.coalesce(func.sum(TceSpDespesa.vl_despesa), 0).label("total"))
            .where(TceSpDespesa.nm_fornecedor.is_not(None), TceSpDespesa.vl_despesa.is_not(None))
            .group_by(TceSpDespesa.nm_fornecedor)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for fornecedor, total in rows:
            print(f"- {fornecedor}: {total}")
        print("")

        print("Top 10 orgaos por valor de despesas:")
        rows = session.execute(
            select(TceSpDespesa.orgao, func.coalesce(func.sum(TceSpDespesa.vl_despesa), 0).label("total"))
            .where(TceSpDespesa.orgao.is_not(None), TceSpDespesa.vl_despesa.is_not(None))
            .group_by(TceSpDespesa.orgao)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for orgao, total in rows:
            print(f"- {orgao}: {total}")
        print("")

        print("Top 10 fontes de receita por valor arrecadado:")
        rows = session.execute(
            select(TceSpReceita.ds_fonte_recurso, func.coalesce(func.sum(TceSpReceita.vl_arrecadacao), 0).label("total"))
            .where(TceSpReceita.ds_fonte_recurso.is_not(None), TceSpReceita.vl_arrecadacao.is_not(None))
            .group_by(TceSpReceita.ds_fonte_recurso)
            .order_by(desc("total"))
            .limit(10)
        ).all()
        for fonte, total in rows:
            print(f"- {fonte}: {total}")
        print("")

        print("Ultimas 10 despesas:")
        latest_despesas = session.scalars(select(TceSpDespesa).order_by(desc(TceSpDespesa.created_at)).limit(10))
        for item in latest_despesas:
            print(
                f"- id={item.id} municipio={item.municipio_slug} ano={item.exercicio} mes={item.mes_numero} "
                f"empenho={item.nr_empenho or '-'} fornecedor={item.nm_fornecedor or '-'} valor={item.vl_despesa or '-'}"
            )
        print("")

        print("Ultimas 10 receitas:")
        latest_receitas = session.scalars(select(TceSpReceita).order_by(desc(TceSpReceita.created_at)).limit(10))
        for item in latest_receitas:
            print(
                f"- id={item.id} municipio={item.municipio_slug} ano={item.exercicio} mes={item.mes_numero} "
                f"fonte={item.ds_fonte_recurso or '-'} valor={item.vl_arrecadacao or '-'}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
