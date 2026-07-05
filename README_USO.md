# Uso operacional do HERMES

## Abrir no navegador

Com a API rodando na VPS:

```text
http://IP_PUBLICO_DA_VPS:8000
```

A tela inicial mostra:

- campo de missao em linguagem natural;
- exemplos clicaveis de investigacao;
- relatorios e alertas;
- fontes monitoradas;
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

Atalhos iniciais:

```text
http://IP_PUBLICO_DA_VPS:8000/relatorios
```

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
