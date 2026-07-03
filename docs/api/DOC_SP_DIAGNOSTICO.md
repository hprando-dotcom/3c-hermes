# Diagnostico do Diario Oficial da Cidade de Sao Paulo

Este documento descreve o diagnostico automatizado do conector DOC SP/APILIB.

## Objetivo

O script `scripts/diagnose_doc_sp.py` substitui testes manuais contra o gateway. Ele gera token OAuth2 por `client_credentials`, testa combinacoes conhecidas de base URL e paths, imprime respostas resumidas e salva um relatorio em `logs/`.

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

Se `SP_DOE_TOKEN_URL` nao for definida, o autenticador tenta candidatos padrao da APILIB:

```text
https://gateway.apilib.prefeitura.sp.gov.br/token
http://gateway.apilib.prefeitura.sp.gov.br/token
https://apilib.prefeitura.sp.gov.br/token
```

O script nunca imprime `SP_DOE_CONSUMER_SECRET` e nunca imprime o token completo.

## Como rodar na VPS

No servidor:

```bash
cd /opt/hermes
python scripts/diagnose_doc_sp.py
```

Se a aplicacao estiver sendo executada apenas dentro do container, rode:

```bash
cd /opt/hermes
docker compose run --rm -v /opt/hermes/logs:/app/logs api python scripts/diagnose_doc_sp.py
```

Esse volume extra garante que o relatorio gerado dentro do container fique persistido em `/opt/hermes/logs` no host.

## O que e testado

Bases:

```text
https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1
http://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1
https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1/
https://servicos.imprensaoficial.com.br/pubnetRestFul
https://servicos.imprensaoficial.com.br/pubnetRestFul/api
https://servicos.imprensaoficial.com.br/pubnetRestFul/api/v1
```

Paths:

```text
/swagger.json
/Publicacao
/Licitacao
/publicacao
/licitacao
/api/Publicacao
/api/Licitacao
```

Datas:

```text
2020-09-01
2026-07-03
```

Cadernos:

```text
11
```

## Saida

Para cada chamada, o diagnostico mostra:

- metodo e URL;
- parametros enviados;
- `status_code`;
- `content-type`;
- tempo de resposta;
- primeiros 500 caracteres da resposta.

O arquivo final segue o formato:

```text
logs/doc_sp_diagnosis_YYYYMMDD_HHMMSS.log
```

## Leitura do resultado

Status `404` em todas as combinacoes autenticadas sugere problema de rota, publicacao da API no gateway ou divergencia entre Swagger e endpoint real.

Status `401` ou `403` sugere problema de credencial, assinatura da aplicacao na API ou escopo do token.

Status `2xx` com corpo valido indica combinacao candidata para o futuro collector real.
