# HERMES

HERMES e um agente de inteligencia publica para investigar publicacoes oficiais, cruzar fontes governamentais e entregar achados, alertas e relatorios acionaveis.

O HERMES nao deve ser tratado como um formulario de consulta manual. A experiencia principal comeca por uma missao em linguagem natural, e as consultas tecnicas PMSP/TCE-SP ficam como modo exploratorio avancado.

## Objetivos da Fase 1

- Estrutura completa do projeto.
- Dockerfile e Docker Compose.
- PostgreSQL preparado com migracao inicial.
- Modelagem inicial para fontes, publicacoes, versoes, arquivos, empresas, classificacoes e execucoes de coleta.
- Modulos `collector`, `parser`, `classifier`, `scheduler`, `database`, `api`, `services`, `config`, `logs`, `scripts` e `docs`.
- Home orientada por missao em `/`.
- Investigacao de fonte oficial por URL em `/investigar`.
- Rota `/missao` para investigacao heuristica inicial.
- Relatorios em `/relatorios`.
- Endpoints operacionais `/status`, `/health`, `/version`, `/openapi.json` e `/docs`.
- Configuracao por `.env`.
- Logging estruturado.
- Scheduler e collector preparados para evolucao.
- Documentacao arquitetural.

## Stack

- Python 3.12
- FastAPI para API operacional, telas HTML e fluxo de missoes
- SQLAlchemy 2
- Alembic
- PostgreSQL 16
- APScheduler
- structlog
- Docker Compose

## Estrutura

```text
.
|-- alembic/
|-- docs/
|-- hermes/
|   |-- api/
|   |-- classifier/
|   |-- collector/
|   |-- config/
|   |-- database/
|   |-- parser/
|   |-- scheduler/
|   `-- services/
|-- logs/
|-- scripts/
|-- tests/
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
`-- README.md
```

## Como executar localmente

Crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Suba a stack:

```powershell
docker compose up --build
```

Verifique a API operacional:

```powershell
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/version
curl http://localhost:8000/openapi.json
```

## Servicos no Compose

- `postgres`: banco PostgreSQL persistido em volume Docker.
- `migrator`: executa `alembic upgrade head` antes da API e do worker.
- `api`: expoe apenas endpoints operacionais.
- `worker`: executa o scheduler continuo.

## Endpoints

- `GET /`: tela inicial HERMES.
- `GET /missao?q=...`: executa uma missao em linguagem natural e devolve resposta executiva.
- `GET /investigar`: investiga URL de Diario Oficial ou portal publico com missao, periodo, DeepSeek opcional e relatorio Markdown.
- `GET /fontes`: lista fontes oficiais inspecionadas.
- `GET /publicacoes`: lista publicacoes oficiais coletadas.
- `GET /publicacoes/resumo`: resume fontes, publicacoes, tipos e alertas.
- `GET /relatorios`: atalhos iniciais de relatorios e investigacoes recorrentes.
- `GET /status`: status operacional, conexao com banco e totais por base.
- `GET /health`: status do servico e conectividade com banco.
- `GET /version`: nome, versao e ambiente.
- `GET /docs`: Swagger UI.
- `GET /openapi.json`: contrato OpenAPI.

Telas de consulta avancada:

- `GET /pmsp`: consulta PMSP Licitacoes.
- `GET /pmsp/resumo`: resumo PMSP Licitacoes.
- `GET /tcesp`: painel TCE-SP.
- `GET /tcesp/municipios`: consulta municipios TCE-SP.
- `GET /tcesp/despesas`: consulta despesas TCE-SP.
- `GET /tcesp/receitas`: consulta receitas TCE-SP.
- `GET /tcesp/resumo`: resumo TCE-SP.

Endpoints JSON TCE-SP:

- `GET /api/tcesp/municipios`
- `GET /api/tcesp/despesas`
- `GET /api/tcesp/receitas`
- `GET /api/tcesp/resumo`

## Desenvolvimento

Instale dependencias em um ambiente virtual, se desejar rodar fora do Docker:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Rode migracoes:

```powershell
python scripts/run_migrations.py
```

Rode a API:

```powershell
uvicorn hermes.main:app --reload
```

Rode o worker:

```powershell
python -m hermes.scheduler.worker
```

Rode testes:

```powershell
pytest
```

## Diagnostico DOC SP

Para diagnosticar o Diario Oficial da Cidade de Sao Paulo via APILIB:

```powershell
python scripts/diagnose_doc_sp.py
```

Na VPS:

```bash
cd /opt/hermes
python scripts/diagnose_doc_sp.py
```

Via Docker, preservando o relatorio no host:

```bash
cd /opt/hermes
docker compose run --rm -v /opt/hermes/logs:/app/logs api python scripts/diagnose_doc_sp.py
```

O script usa `SP_DOE_CONSUMER_KEY` e `SP_DOE_CONSUMER_SECRET` do `.env`, mascara credenciais sensiveis e salva o relatorio em `logs/doc_sp_diagnosis_YYYYMMDD_HHMMSS.log`.

Status atual da Sprint 1B:

- Autenticacao OAuth2 APILIB confirmada.
- Swagger/OpenAPI publico coletado na APILIB Store para `Diario_Oficial - v1`.
- Endpoints documentados: `GET /Publicacao` e `GET /Licitacao`.
- Gateway documentado retornou `404` nas chamadas autenticadas do diagnostico da VPS.
- Hipotese atual: API publicada/desalinhada no gateway ou `basePath` real diferente.
- Fallback publico inicial preparado em `hermes/connectors/doc_sp/public_search.py`.

Mais detalhes em `docs/api/DOC_SP_STATUS.md` e `docs/api/DOC_SP_DIAGNOSTICO.md`.

Scanner profundo da Sprint 1C:

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/scan_doc_sp_deep.py
```

Esse scanner testa bases alternativas, paths comuns, `GET`, `HEAD` e `OPTIONS`, detecta sinais de WSO2/IIS/JSON e salva:

- `logs/doc_sp_deep_scan_YYYYMMDD_HHMMSS.log`
- `logs/doc_sp_deep_scan_summary_YYYYMMDD_HHMMSS.json`

Documentacao: `docs/api/DOC_SP_DEEP_SCAN.md`.

## Diagnostico PMSP Licitacoes

A API `Licitacoes - v1` da APILIB/PMSP usa:

```text
https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1/{ano}
```

O diagnostico compara `grant_type=client_credentials` e `grant_type=password`, testa os anos `2005`, `2010`, `2015` e `2019` com `limite=10&offset=0`, mascara credenciais e salva log + resumo JSON.

Na VPS:

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/diagnose_pmsp_licitacoes.py
```

Arquivos gerados:

- `logs/pmsp_licitacoes_diagnosis_YYYYMMDD_HHMMSS.log`
- `logs/pmsp_licitacoes_diagnosis_summary_YYYYMMDD_HHMMSS.json`

Conector: `hermes/connectors/pmsP_licitacoes/client.py`.
Documentacao: `docs/api/PMSP_LICITACOES_STATUS.md`.

Arquitetura definitiva da Sprint 2B:

- `hermes/connectors/pmsp/licitacoes/apilib.py`: cliente APILIB.
- `hermes/connectors/pmsp/licitacoes/dados_abertos.py`: cliente CKAN Dados Abertos com descoberta dinamica.
- `hermes/connectors/pmsp/licitacoes/provider.py`: fallback APILIB -> CKAN.
- `hermes/connectors/pmsp/licitacoes/normalizer.py`: formato normalizado.
- `hermes/connectors/pmsP_licitacoes/client.py`: wrapper compativel com o conector antigo.

Diagnostico do provider na VPS:

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/diagnose_pmsp_licitacoes_provider.py
```

Arquivos gerados:

- `logs/pmsp_licitacoes_provider_YYYYMMDD_HHMMSS.log`
- `logs/pmsp_licitacoes_provider_summary_YYYYMMDD_HHMMSS.json`

Documentacao: `docs/api/PMSP_LICITACOES_PROVIDER.md`.

Persistencia da Sprint 2C:

- Tabela: `pmsp_licitacoes`.
- Migration: `alembic/versions/202607040001_create_pmsp_licitacoes.py`.
- Service: `hermes/services/pmsp_licitacoes_ingestion.py`.
- Ingestao: `scripts/ingest_pmsp_licitacoes.py`.
- Check DB: `scripts/check_pmsp_licitacoes_db.py`.

Comandos na VPS:

```bash
cd /opt/hermes
git pull
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/ingest_pmsp_licitacoes.py --ano 2015 --limite 100
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/check_pmsp_licitacoes_db.py
```

## TCE-SP Transparencia Municipal

O HERMES tambem possui modulo MVP para a API publica do TCE-SP:

```text
https://transparencia.tce.sp.gov.br/api/json
```

Tabelas:

- `tcesp_municipios`
- `tcesp_despesas`
- `tcesp_receitas`

Conector:

- `hermes/connectors/tcesp/client.py`
- `hermes/connectors/tcesp/normalizer.py`

Comandos na VPS:

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

Uso no navegador:

```text
http://IP_PUBLICO_DA_VPS:8000
http://IP_PUBLICO_DA_VPS:8000/missao?q=obras%20e%20manutencao%20em%20Sao%20Paulo
http://IP_PUBLICO_DA_VPS:8000/tcesp
http://IP_PUBLICO_DA_VPS:8000/status
```

Documentacao: `docs/HERMES_ARQUITETURA_PRODUTO.md`, `docs/HERMES_TCESP.md` e `README_USO.md`.

## Scraping de publicacoes oficiais

O HERMES pode investigar uma fonte oficial informada pelo usuario:

```bash
python scripts/inspect_publication_source.py --url https://exemplo.gov.br/publicacoes
python scripts/collect_publications.py --url https://exemplo.gov.br/publicacoes --limite 100
python scripts/check_publications_db.py
python scripts/run_diario_investigation.py --url https://exemplo.gov.br/publicacoes --mission "obras contratos aditivos engenharia" --date-start 2026-07-01 --date-end 2026-07-10 --limit 50
```

Para usar DeepSeek, defina `DEEPSEEK_API_KEY` no ambiente. Sem a chave, o HERMES gera relatório deterministico com as mesmas evidencias preservadas.

Na VPS:

```bash
cd /opt/hermes
docker compose run --rm api alembic upgrade head
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/collect_publications.py --url https://exemplo.gov.br/publicacoes --limite 100
docker compose run --rm --no-deps -v /opt/hermes/data/reports:/app/data/reports api python scripts/run_diario_investigation.py --url https://exemplo.gov.br/publicacoes --mission "obras contratos aditivos engenharia" --date-start 2026-07-01 --date-end 2026-07-10 --limit 50
```

Documentacao: `docs/HERMES_PUBLICACOES_SCRAPING.md`.

## Principios

- Nunca perder informacao: payload bruto, texto original, texto limpo, metadados e versoes sao preservados.
- Coleta continua: o worker roda separado da API e pode escalar de forma independente.
- Classificacao desacoplada: a integracao futura com DeepSeek entra atras de uma interface propria.
- Banco como memoria historica: PostgreSQL e o nucleo operacional do HERMES.
- HERMES independente: nenhum componente de outro projeto deve ser compartilhado ou misturado.
