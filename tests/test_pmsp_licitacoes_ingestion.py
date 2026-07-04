from __future__ import annotations

from hermes.connectors.pmsp.licitacoes.normalizer import (
    detect_record_format,
    normalize_record,
    normalize_records,
    parse_record,
)
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


def test_normalizer_maps_current_ckan_json_fields() -> None:
    raw = {
        "_id": 1,
        "Nome do Órgão": "COMPANHIA DE ENGENHARIA DE TRAFEGO",
        "Contrato": "68/24",
        "Data da Assinatura": "2024-12-27T00:00:00",
        "Objeto": "Prestacao de servicos",
        "Modalidade": "PREGAO ELETRONICO",
        "Processo Administrativo": "7410.2023/0001816-6",
        "CNPJ/CPF": "12.886.951/0001-99",
        "Fornecedor e Nome de Fantasia": "INTEGRADE SOLUCOES LTDA",
        "Valor(R$)": "127.000,00",
        "Licitação": "057/2020",
        "Data da Publicação": "2024-12-31T00:00:00",
        "Evento": "EXTRATO DE CONTRATO",
    }

    record = normalize_record(raw, ano=2024, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert detect_record_format(raw) == "json_structured"
    assert record["orgao"] == "COMPANHIA DE ENGENHARIA DE TRAFEGO"
    assert record["numero_contrato"] == "68/24"
    assert record["numero_processo"] == "7410.2023/0001816-6"
    assert record["fornecedor_documento"] == "12.886.951/0001-99"
    assert record["numero_licitacao"] == "057/2020"


def test_parser_handles_csv_embedded_in_json_field() -> None:
    raw = {
        "_id": 1,
        "arquivo": (
            "Orgao,Retranca,Modalidade,Numero_Licitacao,Numero_Processo,Objeto,Fornecedor,"
            "Fornecedor_Documento,ValorContrato,NumeroContrato,DataAssinaturaExtrato,"
            "DataPublicacaoExtrato,Evento\n"
            "SANTANA/TUCURUVI,EEHXADM,CONVITE,123/2005,PROC-1,Objeto teste,Fornecedor SA,"
            "00.000.000/0001-00,1000,CT-1,01/02/2005,03/02/2005,EXTRATO"
        ),
    }

    parsed = parse_record(raw)
    record = normalize_record(raw, ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert detect_record_format(raw) == "csv_embedded_json"
    assert parsed["Orgao"] == "SANTANA/TUCURUVI"
    assert record["orgao"] == "SANTANA/TUCURUVI"
    assert record["retranca"] == "EEHXADM"
    assert record["modalidade"] == "CONVITE"
    assert record["numero_processo"] == "PROC-1"
    assert record["numero_contrato"] == "CT-1"


def test_normalize_records_expands_csv_embedded_in_json_field() -> None:
    raw = {
        "_id": 1,
        "arquivo": (
            "Orgao,Retranca,Modalidade,Numero_Licitacao,Numero_Processo,Objeto,Fornecedor,"
            "Fornecedor_Documento,ValorContrato,NumeroContrato,DataAssinaturaExtrato,"
            "DataPublicacaoExtrato,Evento\n"
            "SANTANA/TUCURUVI,EEHXADM,CONVITE,123/2005,PROC-1,Objeto um,Fornecedor A,"
            "00.000.000/0001-00,1000,CT-1,01/02/2005,03/02/2005,EXTRATO\n"
            "SE,EEHXADM,TOMADA,456/2005,PROC-2,Objeto dois,Fornecedor B,"
            "11.111.111/0001-11,2000,CT-2,04/02/2005,05/02/2005,EXTRATO"
        ),
    }

    records = normalize_records([raw], ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert len(records) == 2
    assert records[0]["orgao"] == "SANTANA/TUCURUVI"
    assert records[1]["orgao"] == "SE"
    assert records[1]["numero_licitacao"] == "456/2005"
    assert records[1]["numero_contrato"] == "CT-2"


def test_parser_handles_single_field_csv_without_header() -> None:
    raw = {
        "_id": 1,
        "Orgao": (
            "SANTANA/TUCURUVI,EEHXADM,CONVITE,123/2005,PROC-1,Objeto teste,Fornecedor SA,"
            "00.000.000/0001-00,1000,CT-1,01/02/2005,03/02/2005,EXTRATO"
        ),
    }

    record = normalize_record(raw, ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert detect_record_format(raw) == "single_field_csv"
    assert record["orgao"] == "SANTANA/TUCURUVI"
    assert record["retranca"] == "EEHXADM"
    assert record["modalidade"] == "CONVITE"
    assert record["numero_licitacao"] == "123/2005"
    assert record["numero_processo"] == "PROC-1"
    assert record["fornecedor"] == "Fornecedor SA"
    assert record["fornecedor_documento"] == "00.000.000/0001-00"
    assert record["valor_contrato"] == "1000"
    assert record["data_publicacao"] == "03/02/2005"


def test_parser_handles_sparse_ckan_record_with_csv_inside_orgao() -> None:
    raw = sparse_ckan_csv_record()

    parsed = parse_record(raw)
    record = normalize_record(raw, ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert detect_record_format(raw) == "single_field_csv"
    assert parsed["Orgao"] == "SANTANA/TUCURUVI"
    assert parsed["Modalidade"] == "CONVITE"
    assert record["orgao"] == "SANTANA/TUCURUVI"
    assert record["retranca"] == "EEHXADM"
    assert record["modalidade"] == "CONVITE"
    assert record["numero_licitacao"] == "123/2005"
    assert record["numero_processo"] == "PROC-1"
    assert record["numero_contrato"] == "CT-1"
    assert record["objeto"] == "Objeto teste"


def test_debug_and_ingestion_pipeline_normalize_same_sparse_csv_record() -> None:
    raw = sparse_ckan_csv_record()

    debug_record = normalize_record(raw, ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")
    ingestion_records = normalize_records([raw], ano=2005, source="ckan", source_system="PMSP Dados Abertos CKAN")

    assert ingestion_records == [debug_record]

    persisted = record_to_model_values(ingestion_records[0], build_source_hash(ingestion_records[0]))
    assert persisted["orgao"] == "SANTANA/TUCURUVI"
    assert persisted["modalidade"] == "CONVITE"
    assert persisted["numero_processo"] == "PROC-1"
    assert persisted["numero_contrato"] == "CT-1"
    assert str(persisted["valor_contrato"]) == "1000.00"
    assert str(persisted["data_assinatura"]) == "2005-02-01"
    assert str(persisted["data_publicacao"]) == "2005-02-03"


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


def sparse_ckan_csv_record() -> dict[str, object]:
    return {
        "_id": 1,
        "Orgao": (
            "SANTANA/TUCURUVI,EEHXADM,CONVITE,123/2005,PROC-1,Objeto teste,Fornecedor SA,"
            "00.000.000/0001-00,1000,CT-1,01/02/2005,03/02/2005,EXTRATO"
        ),
        "Retranca": None,
        "Modalidade": None,
        "Numero_Licitacao": None,
        "Numero_Processo": None,
        "Objeto": None,
        "Fornecedor": None,
        "Fornecedor_Documento": None,
        "ValorContrato": None,
        "NumeroContrato": None,
        "DataAssinaturaExtrato": None,
        "DataPublicacaoExtrato": None,
        "Evento": None,
    }
