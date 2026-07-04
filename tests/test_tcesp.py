from __future__ import annotations

from datetime import date
from decimal import Decimal

from hermes.connectors.tcesp.normalizer import normalize_despesa, normalize_municipio, normalize_receita, parse_decimal, slugify
from hermes.services.tcesp_ingestion import ingest_despesas, ingest_municipios


def test_tcesp_normalize_municipio() -> None:
    record = normalize_municipio({"municipio": "balsamo", "municipio_extenso": "Bálsamo"})

    assert record["municipio_slug"] == "balsamo"
    assert record["municipio_extenso"] == "Bálsamo"
    assert record["raw_json"]["municipio"] == "balsamo"


def test_tcesp_normalize_despesa_sample() -> None:
    raw = {
        "orgao": "PREFEITURA MUNICIPAL DE BÁLSAMO",
        "mes": "Janeiro",
        "evento": "Empenhado",
        "nr_empenho": "107-2015",
        "id_fornecedor": "CNPJ - PESSOA JURÍDICA - 02558157000162",
        "nm_fornecedor": "TELEFONICA BRASIL S.A.",
        "dt_emissao_despesa": "05/01/2015",
        "vl_despesa": "60000,00",
    }

    record = normalize_despesa(raw, municipio_slug="balsamo", municipio_extenso="Bálsamo", exercicio=2015, mes=1)

    assert record["municipio_slug"] == "balsamo"
    assert record["municipio_extenso"] == "Bálsamo"
    assert record["orgao"] == "PREFEITURA MUNICIPAL DE BÁLSAMO"
    assert record["nr_empenho"] == "107-2015"
    assert record["dt_emissao_despesa"] == date(2015, 1, 5)
    assert record["vl_despesa"] == Decimal("60000.00")
    assert record["source"] == "tcesp"


def test_tcesp_normalize_receita_sample() -> None:
    raw = {
        "orgao": "PREFEITURA MUNICIPAL DE BÁLSAMO",
        "mes": "Janeiro",
        "ds_fonte_recurso": "01 - TESOURO",
        "ds_cd_aplicacao_fixo": "511 - ASSISTÊNCIA SOCIAL",
        "ds_alinea": "13250100 - REMUNERAÇÃO",
        "ds_subalinea": "13250110 - RECEITA DE REMUNERAÇÃO",
        "vl_arrecadacao": "388,36",
    }

    record = normalize_receita(raw, municipio_slug="balsamo", municipio_extenso="Bálsamo", exercicio=2015, mes=1)

    assert record["municipio_slug"] == "balsamo"
    assert record["ds_fonte_recurso"] == "01 - TESOURO"
    assert record["vl_arrecadacao"] == Decimal("388.36")
    assert record["source"] == "tcesp"


def test_tcesp_decimal_and_slug_helpers() -> None:
    assert parse_decimal("R$ 1.234,56") == Decimal("1234.56")
    assert parse_decimal("388,36") == Decimal("388.36")
    assert slugify("São José do Rio Preto") == "sao-jose-do-rio-preto"


def test_tcesp_ingest_municipios_uses_injected_client() -> None:
    session = TrackingSession()
    result = ingest_municipios(session=session, client=FakeClient())

    assert result["fetched"] == 1
    assert result["inserted"] == 1
    assert session.commit_count == 1
    assert session.added[0].municipio_slug == "balsamo"


def test_tcesp_ingest_despesas_dry_run_uses_injected_client() -> None:
    session = TrackingSession()
    result = ingest_despesas("balsamo", 2015, 1, session=session, client=FakeClient(), dry_run=True)

    assert result["fetched"] == 1
    assert result["skipped"] == 1
    assert session.commit_count == 0


class FakeClient:
    def fetch_municipios(self):
        return [{"municipio": "balsamo", "municipio_extenso": "Bálsamo"}]

    def fetch_despesas(self, _municipio_slug, _exercicio, _mes):
        return [
            {
                "orgao": "PREFEITURA MUNICIPAL DE BÁLSAMO",
                "mes": "Janeiro",
                "evento": "Empenhado",
                "nr_empenho": "107-2015",
                "id_fornecedor": "CNPJ - PESSOA JURÍDICA - 02558157000162",
                "nm_fornecedor": "TELEFONICA BRASIL S.A.",
                "dt_emissao_despesa": "05/01/2015",
                "vl_despesa": "60000,00",
            }
        ]


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class TrackingSession:
    def __init__(self):
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    def execute(self, _statement):
        return FakeResult(None)

    def scalar(self, _statement):
        return "Bálsamo"

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1
