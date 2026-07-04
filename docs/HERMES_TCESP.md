# HERMES TCE-SP

Modulo de consulta e persistencia para a API publica de transparencia municipal do Tribunal de Contas do Estado de Sao Paulo.

## Fonte oficial

Base publica:

```text
https://transparencia.tce.sp.gov.br/api/json
```

Endpoints consumidos:

- `GET /municipios`
- `GET /despesas/{municipio}/{exercicio}/{mes}`
- `GET /receitas/{municipio}/{exercicio}/{mes}`

Exemplo:

```text
https://transparencia.tce.sp.gov.br/api/json/despesas/balsamo/2015/1
```

## Banco de dados

As tabelas criadas pela migration `202607050001_create_tcesp_tables.py` sao:

- `tcesp_municipios`
- `tcesp_despesas`
- `tcesp_receitas`

Os payloads brutos sao preservados em `raw_json`. Despesas e receitas tambem gravam municipio, exercicio, mes e campos principais normalizados para consulta no navegador.

## Conector

Codigo:

- `hermes/connectors/tcesp/client.py`
- `hermes/connectors/tcesp/normalizer.py`

O client usa `httpx`, `Accept: application/json`, `User-Agent: HERMES/0.1`, timeout e tentativas simples. O normalizer trata datas `DD/MM/YYYY`, numeros no formato brasileiro e slugs de municipio.

## Ingestao na VPS

Sequencia recomendada:

```bash
cd /opt/hermes
git pull
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/ingest_tcesp_municipios.py
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/ingest_tcesp_despesas.py --municipio balsamo --ano 2015 --mes 1 --limite 100
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/ingest_tcesp_receitas.py --municipio balsamo --ano 2015 --mes 1 --limite 100
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/check_tcesp_db.py
```

Cada script de ingestao salva:

- `logs/tcesp_*_ingest_YYYYMMDD_HHMMSS.log`
- `logs/tcesp_*_ingest_summary_YYYYMMDD_HHMMSS.json`

## Interface web

Com a API em execucao:

- `/`: hub HERMES.
- `/tcesp`: painel TCE-SP.
- `/tcesp/municipios`: busca de municipios.
- `/tcesp/despesas`: busca de despesas por municipio, ano, mes, termo e fornecedor.
- `/tcesp/receitas`: busca de receitas por municipio, ano, mes e termo.
- `/tcesp/resumo`: totais e rankings.
- `/status`: saude operacional e totais das tabelas.
- `/docs`: Swagger UI do FastAPI.

## Endpoints JSON

- `/api/tcesp/municipios`
- `/api/tcesp/despesas`
- `/api/tcesp/receitas`
- `/api/tcesp/resumo`

Esses endpoints retornam `ok=false` com detalhes controlados quando a tabela ainda nao existe ou o banco esta indisponivel.

## Limitacoes conhecidas

- O MVP ingere municipio/ano/mes por comando, sem agenda automatica TCE-SP ainda.
- A deduplicacao usa uma chave logica conservadora por campos principais; ela evita duplicacao operacional, mas ainda pode evoluir para hash explicito caso a fonte altere granularidade.
- A consulta HTML e propositalmente simples e sem autenticacao nesta etapa.
- Licitacoes e contratos TCE-SP/Audesp Fase IV existem em conjuntos de dados por download a partir de janeiro de 2018. O MVP registra essa fonte como caminho futuro, mas nao baixa bases grandes automaticamente.
