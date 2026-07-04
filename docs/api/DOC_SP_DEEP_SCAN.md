# Scanner profundo DOC-SP/APILIB

Este documento descreve o scanner profundo criado na Sprint 1C para descobrir o endpoint real do DOC-SP no gateway APILIB sem depender de testes manuais avulsos.

## Objetivo

O script `scripts/scan_doc_sp_deep.py` executa uma varredura autenticada no gateway APILIB usando o token OAuth2 ja validado nos sprints anteriores.

Ele testa combinacoes de:

- bases do gateway;
- paths comuns de descoberta, documentacao e dominio DOC-SP;
- metodos `GET`, `HEAD` e `OPTIONS`;
- headers `Authorization: Bearer <token>`, `Accept: application/json` e `Content-Type: application/json`.

## Variaveis de ambiente

Obrigatorias:

```text
SP_DOE_CONSUMER_KEY=
SP_DOE_CONSUMER_SECRET=
```

Opcional:

```text
SP_DOE_TOKEN_URL=
```

O script nunca imprime o token completo, nunca imprime `SP_DOE_CONSUMER_SECRET` e mascara previews que possam conter credenciais.

## Como rodar na VPS

Comando recomendado:

```bash
cd /opt/hermes
docker compose run --rm --no-deps -v /opt/hermes/logs:/app/logs api python scripts/scan_doc_sp_deep.py
```

Tambem pode ser executado fora do Docker se o ambiente Python estiver preparado:

```bash
cd /opt/hermes
python scripts/scan_doc_sp_deep.py
```

## Escopo da varredura

Bases testadas:

```text
https://gateway.apilib.prefeitura.sp.gov.br
https://gateway.apilib.prefeitura.sp.gov.br/sg
https://gateway.apilib.prefeitura.sp.gov.br/sg/dom
https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1
https://gateway.apilib.prefeitura.sp.gov.br/dom
https://gateway.apilib.prefeitura.sp.gov.br/dom/v1
https://gateway.apilib.prefeitura.sp.gov.br/diario-oficial
https://gateway.apilib.prefeitura.sp.gov.br/diario-oficial/v1
https://gateway.apilib.prefeitura.sp.gov.br/Diario_Oficial
https://gateway.apilib.prefeitura.sp.gov.br/Diario_Oficial/v1
```

Paths testados:

```text
/swagger
/swagger.json
/openapi.json
/api-docs
/v2/api-docs
/v3/api-docs
/services
/metadata
/health
/status
/version
/Publicacao
/Publicacoes
/publicacao
/publicacoes
/Licitacao
/Licitacoes
/licitacao
/licitacoes
/Materia
/Materias
/materia
/materias
/Consulta
/Pesquisa
/Busca
/Edicao
/Edicoes
/Caderno
/Cadernos
```

Total planejado:

```text
10 bases x 30 paths x 3 metodos = 900 chamadas
```

## Saidas

Log completo:

```text
logs/doc_sp_deep_scan_YYYYMMDD_HHMMSS.log
```

Resumo JSON:

```text
logs/doc_sp_deep_scan_summary_YYYYMMDD_HHMMSS.json
```

Cada probe registra:

- URL;
- metodo;
- status;
- `content-type`;
- `elapsed_ms`;
- tamanho da resposta;
- preview mascarado;
- se parece WSO2;
- se parece HTML IIS;
- se parece JSON;
- palavras-chave encontradas;
- motivos para classificar como candidato interessante.

## Candidatos interessantes

O scanner destaca respostas quando houver qualquer uma destas condicoes:

- status diferente de `404`;
- status `200`, `201` ou `204`;
- status `401`, `403` ou `405`;
- `content-type` JSON;
- resposta contendo termos como `swagger`, `openapi`, `publicacao`, `licitacao`, `diario`, `materia` ou `caderno`.

## Leitura pratica

No servidor, comece pelo resumo:

```bash
cd /opt/hermes
python -m json.tool logs/doc_sp_deep_scan_summary_YYYYMMDD_HHMMSS.json | less
```

Campos mais importantes:

- `status_counts`: distribuicao geral dos status HTTP.
- `interesting_count`: quantidade de candidatos.
- `candidates`: lista prioritaria para investigacao.
- `wso2_detected`: indica se alguma resposta tem sinais de WSO2/API Manager.
- `html_iis_detected`: indica se alguma resposta parece pagina HTML do IIS.
- `json_detected`: indica se alguma resposta trouxe JSON.

Se algum candidato indicar `successful_status`, `json_content`, ou keywords de dominio, ele deve ser usado como primeira pista para implementar o collector real.
