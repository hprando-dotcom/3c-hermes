# Uso operacional do HERMES

## Abrir no navegador

Com a API rodando na VPS:

```text
http://IP_PUBLICO_DA_VPS:8000
```

A tela inicial mostra:

- chamada principal para o cockpit `/investigar`;
- botao `Comecar investigacao`;
- historico de dossies em `/relatorios`;
- fontes monitoradas;
- publicacoes coletadas;
- modo exploratorio avancado PMSP/TCE-SP;
- status operacional;
- link para `/docs`.

## Missoes

A experiencia principal e escrever o que o HERMES deve investigar:

```text
http://IP_PUBLICO_DA_VPS:8000/missao?q=obras%20e%20manutencao%20em%20Sao%20Paulo
```

Exemplos:

- `obras e manutencao em Sao Paulo`
- `fornecedores recorrentes em contratos publicos`
- `movimentacoes de saude`
- `despesas municipais no TCE-SP`
- `orgaos mais ativos`

O HERMES devolve resumo executivo, bases consultadas, achados, rankings, evidencias, alertas de qualidade e proximas perguntas sugeridas.

## Relatorios

Historico de dossies gerados:

```text
http://IP_PUBLICO_DA_VPS:8000/relatorios
```

Cada item mostra missao, fonte, periodo, total de achados, uso de DeepSeek e botoes para abrir HTML ou baixar Markdown, CSV, JSON e ZIP.

## Investigar Diario Oficial

Use a home ou acesse diretamente:

```text
http://IP_PUBLICO_DA_VPS:8000/investigar
```

Com URL:

```text
http://IP_PUBLICO_DA_VPS:8000/investigar?source_url=https://exemplo.gov.br/publicacoes&mission=obras%20contratos%20aditivos%20engenharia&date_start=2026-07-01&date_end=2026-07-10&limit=50
```

O HERMES detecta links, PDFs e publicacoes candidatas, extrai texto, classifica achados com DeepSeek quando `DEEPSEEK_API_KEY` existe e gera um dossie baixavel com Markdown, HTML, CSV, JSON e ZIP.

```bash
docker compose run --rm --no-deps -v /opt/hermes/data:/app/data api python scripts/run_diario_investigation.py --url https://exemplo.gov.br/publicacoes --mission "obras contratos aditivos engenharia" --date-start 2026-07-01 --date-end 2026-07-10 --limit 50
```

Consultas:

- `/fontes`
- `/publicacoes`
- `/publicacoes/resumo`

## TCE-SP

Depois de aplicar a migration e ingerir dados, use:

- `http://IP_PUBLICO_DA_VPS:8000/tcesp`
- `http://IP_PUBLICO_DA_VPS:8000/tcesp/municipios`
- `http://IP_PUBLICO_DA_VPS:8000/tcesp/despesas?municipio=balsamo&ano=2015&mes=1`
- `http://IP_PUBLICO_DA_VPS:8000/tcesp/receitas?municipio=balsamo&ano=2015&mes=1`
- `http://IP_PUBLICO_DA_VPS:8000/tcesp/resumo?ano=2015`

## PMSP

Consultas principais:

- `http://IP_PUBLICO_DA_VPS:8000/pmsp?ano=2015&limite=50`
- `http://IP_PUBLICO_DA_VPS:8000/pmsp/resumo?ano=2015`

## Status e API

- `/status`: pagina de status e totais das tabelas.
- `/health`: saude operacional em JSON.
- `/version`: metadados do servico em JSON.
- `/openapi.json`: contrato OpenAPI.
- `/docs`: Swagger UI.
