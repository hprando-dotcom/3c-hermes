# Provider PMSP Licitacoes

Atualizado em 2026-07-04.

## Objetivo

A Sprint 2B substitui a visao de fonte unica por uma arquitetura com provider e fallback para PMSP Licitacoes.

O diagnostico da Sprint 2A mostrou que:

- OAuth APILIB funciona;
- os anos `2005`, `2010` e `2015` retornaram HTTP `200`;
- a resposta efetiva tem formato CKAN: `help`, `success`, `result`;
- a fonte consultada por baixo e o Portal de Dados Abertos PMSP;
- o ano `2019` retornou `404` porque o `resource_id` usado pela rota nao foi encontrado;
- depender de `resource_id` fixo e fragil.

Na Sprint 2C, a nomenclatura foi corrigida: quando a URL real ou o payload indicam `dados.prefeitura.sp.gov.br`, o registro normalizado usa `source="ckan"` e `source_system="PMSP Dados Abertos CKAN"`, mesmo que a chamada tenha passado pelo gateway APILIB.

## Camadas

### APILIB

Arquivo:

```text
hermes/connectors/pmsp/licitacoes/apilib.py
```

Responsabilidades:

- chamar `https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1/{ano}`;
- enviar token APILIB em `Authorization: Bearer <token>`;
- usar `limite` e `offset`;
- extrair registros quando o payload vier em envelope CKAN;
- normalizar os registros retornados.
- classificar a origem efetiva como CKAN quando o gateway APILIB encaminhar para Dados Abertos.

### Dados Abertos CKAN

Arquivo:

```text
hermes/connectors/pmsp/licitacoes/dados_abertos.py
```

Base:

```text
https://dados.prefeitura.sp.gov.br/api/action
```

Metodos:

- `package_search(query)`;
- `package_show(package_id)`;
- `datastore_search(resource_id, limit, offset, q=None)`;
- `discover_resources()`;
- `list_by_year(ano, limite=100, offset=0)`.

## Descoberta dinamica

O conector CKAN nao depende apenas de `resource_id` fixo. Ele procura datasets relacionados a:

- `licitações`;
- `licitacoes`;
- `compras`;
- `contratos`;
- `e-negocios`;
- `e-negócios`;
- `compras e licitações`.

Os resources sao ranqueados por:

- nome, titulo ou descricao contendo ano entre `2005` e `2019`;
- formato util: `JSON`, `CSV`, `XLS`, `XLSX`;
- campos esperados encontrados via `datastore_search` com `limit=1`.

Campos esperados:

```text
Orgao
Retranca
Modalidade
Número_Licitação
objeto
Fornecedor
ValorContrato
NumeroContrato
DataAssinaturaExtrato
DataPublicacaoExtrato
```

## Provider e fallback

Arquivo:

```text
hermes/connectors/pmsp/licitacoes/provider.py
```

Ordem de tentativa:

1. APILIB;
2. CKAN Dados Abertos.

O fallback CKAN e usado quando APILIB falha, retorna erro, `404` ou `5xx`. Se ambas as fontes falharem, o provider retorna erro estruturado com os detalhes das tentativas.

## Normalizacao

Arquivo:

```text
hermes/connectors/pmsp/licitacoes/normalizer.py
```

Cada registro normalizado possui:

```text
source
source_system
ano
orgao
modalidade
numero_licitacao
numero_processo
numero_contrato
objeto
fornecedor
fornecedor_documento
valor_contrato
data_assinatura
data_publicacao
evento
retranca
raw
```

O campo `raw` preserva o registro original para auditoria e ajustes futuros de mapeamento.

## Compatibilidade

O conector antigo continua existindo:

```text
hermes/connectors/pmsP_licitacoes/client.py
```

Ele agora delega para o provider novo e mantém a interface `PmspLicitacoesClient.list_by_year(...)`.

## Diagnostico

Script:

```text
scripts/diagnose_pmsp_licitacoes_provider.py
```

O script:

- carrega `.env`;
- tenta obter token APILIB;
- testa os anos `2005`, `2010`, `2015` e `2019`;
- executa o provider completo;
- indica a fonte usada: `apilib` ou `ckan`;
- informa status, total, quantidade retornada e erros;
- salva log e resumo JSON.

Arquivos gerados:

```text
logs/pmsp_licitacoes_provider_YYYYMMDD_HHMMSS.log
logs/pmsp_licitacoes_provider_summary_YYYYMMDD_HHMMSS.json
```

## Persistencia

Tabela:

```text
pmsp_licitacoes
```

Modelo ORM:

```text
hermes/database/models.py::PmspLicitacao
```

Migration:

```text
alembic/versions/202607040001_create_pmsp_licitacoes.py
```

Servico:

```text
hermes/services/pmsp_licitacoes_ingestion.py
```

O servico usa o provider PMSP Licitacoes, grava registros normalizados, calcula `source_hash`, faz upsert por hash e evita duplicacao logica.

Script de ingestao:

```text
scripts/ingest_pmsp_licitacoes.py
```

Exemplo:

```bash
python scripts/ingest_pmsp_licitacoes.py --ano 2015 --limite 100
```

Diagnostico de banco:

```text
scripts/check_pmsp_licitacoes_db.py
```

## Como rodar na VPS

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/diagnose_pmsp_licitacoes_provider.py
```

## Limitacoes conhecidas

- A descoberta CKAN usa heuristicas de nome, descricao, formato e campos; se a PMSP renomear datasets ou campos, pode ser necessario ajustar o ranking.
- Resources em CSV/XLS podem ser descobertos, mas a coleta atual prioriza `datastore_search`; resources nao carregados no datastore podem exigir coletor especifico futuro.
- O provider ainda nao pagina automaticamente todos os registros; ele respeita `limite` e `offset`.
- A normalizacao preserva valores como texto quando o formato original ainda nao foi estabilizado.
