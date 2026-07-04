# Uso operacional do HERMES

## Abrir no navegador

Com a API rodando na VPS:

```text
http://IP_PUBLICO_DA_VPS:8000
```

A tela inicial mostra:

- consulta PMSP Licitacoes;
- modulo TCE-SP;
- status operacional;
- link para `/docs`.

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
