# Diagnostico do Diario Oficial da Cidade de Sao Paulo

Este documento descreve o diagnostico automatizado do conector DOC SP/APILIB.

## Objetivo

O script `scripts/diagnose_doc_sp.py` substitui testes manuais contra o gateway. Ele gera token OAuth2 por `client_credentials`, tenta coletar Swagger/OpenAPI pela APILIB Store publica, testa descoberta avancada de base paths, headers e querystring, imprime respostas resumidas e salva um relatorio em `logs/`.

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

Descoberta publica de Swagger/OpenAPI:

```text
https://apilib.prefeitura.sp.gov.br/store/api-docs/admin/Diario_Oficial/v1
https://apilib.prefeitura.sp.gov.br/store/apis/info?name=Diario_Oficial&provider=admin&version=v1
https://apilib.prefeitura.sp.gov.br/store/api-docs?name=Diario_Oficial&provider=admin&version=v1
https://apilib.prefeitura.sp.gov.br/store/api-docs/admin/Diario_Oficial/v1/swagger.json
```

Base paths no gateway:

```text
/Diario_Oficial/v1
/diario_oficial/v1
/diario-oficial/v1
/dom/v1
/sgdom/v1
/sg/dom/v1
/SG/DOM/v1
/SG_DOM/v1
```

Paths:

```text
/swagger.json
/Publicacao
/Licitacao
```

Datas:

```text
2020-09-01
2026-07-03
```

Cadernos:

```text
11 como inteiro
11 como string
```

Perfis de headers:

```text
Accept: application/json
Content-Type: application/json
apikey: <access_token>
Authorization: Bearer <token>
```

## Saida

Para cada chamada, o diagnostico mostra:

- metodo e URL;
- parametros enviados;
- perfil de headers usado, com credenciais mascaradas;
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

O resumo final informa se o Swagger foi coletado, os endpoints documentados testados, a quantidade de chamadas `2xx`, a quantidade de `404` e a distribuicao de status.
