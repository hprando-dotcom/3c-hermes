# HERMES - Scraping e investigacao de publicacoes oficiais

## Objetivo

Esta camada permite que o usuario informe a URL de uma fonte oficial e o HERMES investigue a pagina em busca de publicacoes, PDFs, links relevantes e endpoints candidatos.

O fluxo reposiciona o HERMES como agente investigador:

1. usuario informa uma missao e/ou URL de fonte oficial;
2. HERMES inspeciona a fonte;
3. detecta links, PDFs e endpoints;
4. normaliza publicacoes candidatas;
5. deduplica por hash;
6. persiste evidencias em `publications`;
7. mostra fontes e publicacoes na UI.

Fluxo inteligente do MVP:

```text
URL + periodo + missao
-> coleta HTML/PDF
-> extracao de texto
-> triagem por termos
-> DeepSeek classifica/interpreta quando DEEPSEEK_API_KEY existe
-> fallback deterministico quando IA indisponivel
-> dossie Markdown/HTML/CSV/JSON/ZIP com evidencias
```

## Camada de conectores

Arquivos:

- `hermes/connectors/publications/source_inspector.py`
- `hermes/connectors/publications/html_scraper.py`
- `hermes/connectors/publications/endpoint_scraper.py`
- `hermes/connectors/publications/normalizer.py`
- `hermes/connectors/publications/hashing.py`

### `source_inspector.py`

Baixa a URL oficial ou analisa HTML recebido em teste. Retorna:

- status HTTP;
- content-type;
- titulo;
- links;
- PDFs;
- publicacoes candidatas;
- endpoints candidatos;
- preview de texto visivel.

### `html_scraper.py`

Extrai links HTML com `html.parser` da biblioteca padrao. Marca:

- links PDF;
- links do mesmo dominio;
- links com aparencia de publicacao oficial.

### `endpoint_scraper.py`

Detecta endpoints por:

- referencias no HTML;
- caminhos comuns como `/openapi.json`, `/swagger.json`, `/wp-json`, `/api/publicacoes`.

Opcionalmente faz probe HTTP dos primeiros candidatos.

### `normalizer.py`

Converte candidatos em formato normalizado:

- `source_url`;
- `url`;
- `title`;
- `text`;
- `publication_type`;
- `published_at`;
- `year`;
- `links`;
- `content_hash`;
- `raw`.

### `hashing.py`

Normaliza URL e gera SHA-256 estavel para deduplicacao.

## Banco de dados

Tabela nova:

- `public_sources`

Tabela existente reutilizada:

- `publications`

A tabela `publications` ja existia no schema inicial do HERMES e possui campos adequados para fonte, tipo, objeto, links, payload bruto, payload normalizado, texto, hash e timestamps.

Migration:

- `alembic/versions/202607100001_create_public_sources.py`

## Scripts

Inspecionar fonte:

```bash
python scripts/inspect_publication_source.py --url https://exemplo.gov.br/publicacoes
```

Coletar publicacoes candidatas:

```bash
python scripts/collect_publications.py --url https://exemplo.gov.br/publicacoes --limite 100
```

Dry-run:

```bash
python scripts/collect_publications.py --url https://exemplo.gov.br/publicacoes --dry-run
```

Checar banco:

```bash
python scripts/check_publications_db.py
```

Executar investigacao inteligente de Diario Oficial:

```bash
python scripts/run_diario_investigation.py \
  --url "https://exemplo.gov.br/publicacoes" \
  --mission "obras contratos aditivos engenharia" \
  --date-start "2026-07-01" \
  --date-end "2026-07-10" \
  --limit 50
```

## DeepSeek

A camada de IA fica em:

- `hermes/services/deepseek_service.py`

Variaveis:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`, padrao `https://api.deepseek.com`
- `DEEPSEEK_MODEL_FAST`, padrao `deepseek-v4-flash`
- `DEEPSEEK_MODEL_REPORT`, padrao `deepseek-v4-pro` ou fallback para o modelo fast

Sem `DEEPSEEK_API_KEY`, o HERMES continua funcionando em modo deterministico. Falhas 401, 429, 500, timeout ou JSON invalido entram como limitacao no relatorio e nao interrompem a investigacao.

Serviço principal:

- `hermes/services/official_gazette_investigation.py`

Saida:

- achados classificados;
- evidencias com links;
- limitacoes;
- metricas de custo aproximadas;
- dossie salvo em `data/reports/` e `data/exports/`.

Arquivos gerados por investigacao:

- `data/reports/{investigation_id}.md`
- `data/reports/{investigation_id}.html`
- `data/exports/{investigation_id}_achados.csv`
- `data/exports/{investigation_id}.json`
- `data/exports/{investigation_id}_dossie.zip`

## Rotas web

- `/investigar`: cockpit e resultado de investigacao de Diario Oficial.
- `/downloads/{filename}`: download seguro dos arquivos de dossie em `data/reports` ou `data/exports`.
- `/relatorios`: historico dos dossies gerados.
- `/fontes`: fontes oficiais investigadas.
- `/publicacoes`: publicacoes coletadas.
- `/publicacoes/resumo`: resumo de fontes, publicacoes, tipos e alertas.
- `/status`: inclui fontes oficiais e publicacoes oficiais.

## VPS

Sequencia sugerida:

```bash
cd /opt/hermes
git pull
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

Coletar por Docker:

```bash
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/inspect_publication_source.py --url https://exemplo.gov.br/publicacoes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/collect_publications.py --url https://exemplo.gov.br/publicacoes --limite 100
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/check_publications_db.py
docker compose run --rm --no-deps -v /opt/hermes/data:/app/data api python scripts/run_diario_investigation.py --url https://exemplo.gov.br/publicacoes --mission "obras contratos aditivos engenharia" --date-start 2026-07-01 --date-end 2026-07-10 --limit 50
```

## Limites atuais

- O scraping inicial e conservador e baseado em HTML, links e endpoints candidatos.
- Nao executa JavaScript de paginas dinamicas.
- Tenta extrair texto de PDFs com `pypdf`, mas PDF-imagem/OCR fica como limitacao registrada.
- Endpoints candidatos podem exigir autenticacao ou parametros.
- A coleta pesada e controlada por `--limite`.
- PDF nativo nao e gerado nesta etapa; o HTML do relatorio e imprimivel pelo navegador.
