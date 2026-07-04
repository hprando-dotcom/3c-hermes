# Status da API PMSP Licitacoes

Atualizado em 2026-07-04.

## Estado confirmado

A aplicacao `HERMES-PROD` foi inscrita na API `Licitacoes - v1` da APILIB/PMSP.

Swagger confirmado:

```text
server: https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1
endpoint: GET /{ano}
```

Parametros:

```text
ano: path integer, de 2005 a 2019
limite: query integer opcional
offset: query integer opcional
```

Exemplo:

```text
GET https://gateway.apilib.prefeitura.sp.gov.br/sg/licitacoes/v1/2019?limite=100&offset=0
```

## Autenticacao

O diagnostico usa as credenciais APILIB ja existentes no `.env`:

```text
SP_DOE_CONSUMER_KEY=
SP_DOE_CONSUMER_SECRET=
SP_DOE_USERNAME=
SP_DOE_PASSWORD=
SP_DOE_TOKEN_URL=
```

Sao testados dois modos OAuth2:

- `grant_type=client_credentials`;
- `grant_type=password`.

Tokens, senha, consumer secret e previews sensiveis sao mascarados no terminal, no log e no resumo JSON.

## Conector

Conector inicial:

```text
hermes/connectors/pmsP_licitacoes/client.py
```

Responsabilidades atuais:

- montar a URL `/{ano}`;
- validar o intervalo de anos `2005..2019`;
- enviar `Authorization: Bearer <token>`;
- aplicar `Accept: application/json` e `Content-Type: application/json`;
- detectar resposta JSON;
- contar registros retornados quando o payload for lista ou contiver listas em chaves comuns.

## Diagnostico

Script:

```text
scripts/diagnose_pmsp_licitacoes.py
```

O script:

- carrega `.env`;
- gera token por `client_credentials`;
- gera token por `password`;
- testa os anos `2005`, `2010`, `2015` e `2019`;
- usa `limite=10` e `offset=0`;
- imprime status, `content-type`, tempo, tamanho, preview e quantidade de registros;
- salva log completo e resumo JSON.

Arquivos gerados:

```text
logs/pmsp_licitacoes_diagnosis_YYYYMMDD_HHMMSS.log
logs/pmsp_licitacoes_diagnosis_summary_YYYYMMDD_HHMMSS.json
```

## Como rodar na VPS

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/diagnose_pmsp_licitacoes.py
```

Depois, abrir o resumo:

```bash
python -m json.tool "$(ls -t logs/pmsp_licitacoes_diagnosis_summary_*.json | head -1)"
```

## Criterios de leitura

- `status_code` 2xx com `looks_json=true` indica candidato para collector real.
- `record_count` informa quantos itens foram detectados no payload JSON.
- Diferenca entre `client_credentials` e `password` ajuda a confirmar se a API exige contexto de usuario.
- `401` ou `403` sugere problema de assinatura, escopo ou modo OAuth.
