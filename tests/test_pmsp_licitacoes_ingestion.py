from __future__ import annotations

from hermes.connectors.pmsp.licitacoes.normalizer import normalize_record
from hermes.connectors.pmsp.licitacoes.apilib import classify_effective_source
from hermes.database.models import PmspLicitacao
from hermes.services.pmsp_licitacoes_ingestion import build_source_hash, record_to_model_values, upsert_record


def test_normalizer_maps_pmsp_licitacoes_fields() -> None:
    raw = {
        "Orgao": "Secretaria Municipal de Obras",
        "Retranca": "CONTRATO",
        "Modalidade": "Pregao",
        "N\u00famero_Licita\u00e7\u00e3o": "123/2015",
        "objeto": "Pavimentacao",
        "Fornecedor": "Empresa Teste",
        "ValorContrato": "R$ 1.234,56",
        "NumeroContrato": "45/2015",
        "DataAssinaturaExtrato": "10/02/2015",
        "DataPublicacaoExtrato": "2015-02-11",
    }

    record = normalize_record(raw, ano=2015, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert record["source"] == "ckan"
    assert record["source_system"] == "PMSP Dados Abertos CKAN"
    assert record["ano"] == 2015
    assert record["orgao"] == "Secretaria Municipal de Obras"
    assert record["numero_licitacao"] == "123/2015"
    assert record["numero_contrato"] == "45/2015"
    assert record["raw"] == raw


def test_build_source_hash_is_stable_for_same_identity() -> None:
    record_a = {
        "source": "ckan",
        "source_system": "PMSP Dados Abertos CKAN",
        "ano": 2015,
        "orgao": "A",
        "numero_processo": "1",
        "numero_contrato": "2",
        "raw": {"_id": 99, "x": "y"},
    }
    record_b = {
        "raw": {"x": "changed", "_id": 99},
        "numero_contrato": "2",
        "numero_processo": "1",
        "orgao": "A",
        "ano": 2015,
        "source_system": "PMSP Dados Abertos CKAN",
        "source": "ckan",
    }

    assert build_source_hash(record_a) == build_source_hash(record_b)


def test_effective_source_is_ckan_when_real_url_is_dados_abertos() -> None:
    source, source_system = classify_effective_source(
        "https://dados.prefeitura.sp.gov.br/api/action/datastore_search",
        {"help": "https://dados.prefeitura.sp.gov.br/api/action/help_show?name=datastore_search"},
    )

    assert source == "ckan"
    assert source_system == "PMSP Dados Abertos CKAN"


def test_upsert_record_skips_existing_identical_record() -> None:
    record = {
        "source": "ckan",
        "source_system": "PMSP Dados Abertos CKAN",
        "ano": 2015,
        "orgao": "Secretaria",
        "modalidade": "Pregao",
        "numero_licitacao": "123",
        "numero_processo": "456",
        "numero_contrato": "789",
        "objeto": "Objeto",
        "fornecedor": "Fornecedor",
        "fornecedor_documento": "00.000.000/0001-00",
        "valor_contrato": "100,00",
        "data_assinatura": "2015-01-02",
        "data_publicacao": "03/01/2015",
        "evento": "Contrato",
        "retranca": "Retranca",
        "raw": {"_id": 1},
    }
    source_hash = build_source_hash(record)
    existing = PmspLicitacao(**record_to_model_values(record, source_hash))
    session = FakeSession(existing)

    result = upsert_record(session, record)

    assert result == "skipped"
    assert session.added == []


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []
        self.flushed = False

    def execute(self, _statement):
        return FakeResult(self.existing)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flushed = True
