# HERMES

HERMES e uma plataforma operacional de inteligencia para rastrear publicacoes oficiais relacionadas a engenharia e infraestrutura.

Este repositorio contem a fundacao da Fase 1. Ele nao e uma interface grafica, nao e um CRUD tradicional e nao depende do computador local para operar. O desenho alvo e execucao continua em VPS, com PostgreSQL, coletores, parser, classificador desacoplado, scheduler e API operacional minima.

## Objetivos da Fase 1

- Estrutura completa do projeto.
- Dockerfile e Docker Compose.
- PostgreSQL preparado com migracao inicial.
- Modelagem inicial para fontes, publicacoes, versoes, arquivos, empresas, classificacoes e execucoes de coleta.
- Modulos `collector`, `parser`, `classifier`, `scheduler`, `database`, `api`, `services`, `config`, `logs`, `scripts` e `docs`.
- Endpoints operacionais `/health` e `/version`.
- Configuracao por `.env`.
- Logging estruturado.
- Scheduler e collector preparados para evolucao.
- Documentacao arquitetural.

## Stack

- Python 3.12
- FastAPI somente para API operacional
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
curl http://localhost:8000/health
curl http://localhost:8000/version
```

## Servicos no Compose

- `postgres`: banco PostgreSQL persistido em volume Docker.
- `migrator`: executa `alembic upgrade head` antes da API e do worker.
- `api`: expoe apenas endpoints operacionais.
- `worker`: executa o scheduler continuo.

## Endpoints

- `GET /health`: status do servico e conectividade com banco.
- `GET /version`: nome, versao e ambiente.

O FastAPI Docs UI foi desabilitado de proposito para respeitar a premissa de nao criar interface grafica. O contrato OpenAPI permanece em `/openapi.json`.

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

## Principios

- Nunca perder informacao: payload bruto, texto original, texto limpo, metadados e versoes sao preservados.
- Coleta continua: o worker roda separado da API e pode escalar de forma independente.
- Classificacao desacoplada: a integracao futura com DeepSeek entra atras de uma interface propria.
- Banco como memoria historica: PostgreSQL e o nucleo operacional do HERMES.
- HERMES independente: nenhum componente de outro projeto deve ser compartilhado ou misturado.
