# Status da API DOC-SP

Atualizado em 2026-07-04.

## Estado confirmado

- Autenticacao OAuth2 APILIB confirmada via `client_credentials`.
- Token obtido com sucesso usando `SP_DOE_CONSUMER_KEY` e `SP_DOE_CONSUMER_SECRET`.
- Swagger/OpenAPI coletado na APILIB Store publica:
  - `https://apilib.prefeitura.sp.gov.br/store/api-docs/admin/Diario_Oficial/v1`
- API publicada na Store como `Diario_Oficial - v1`.

## Contrato documentado

Servers informados pelo Swagger:

```text
https://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1
http://gateway.apilib.prefeitura.sp.gov.br/sg/dom/v1
```

Endpoints documentados:

```text
GET /Publicacao
GET /Licitacao
```

Parametros documentados:

```text
dataPublicacao: string date, formato AAAA-MM-DD
caderno: integer, exemplo 11
```

## Falha observada

O diagnostico executado na VPS gerou:

```text
logs/doc_sp_diagnosis_20260704_142511.log
```

Resultado observado:

- OAuth2 funcionando.
- Swagger coletado e coerente com a APILIB Store.
- 78 chamadas autenticadas testadas contra combinacoes conhecidas retornaram `404`.
- A falha ocorreu mesmo usando os paths documentados `/Publicacao` e `/Licitacao`.

## Hipotese atual

A API pode estar publicada/desalinhada no gateway, ou o `basePath` real pode ser diferente do informado no Swagger publico.

Tambem e possivel que exista uma regra de roteamento interna da APILIB, ambiente, plano, assinatura ou publicacao que aceite o token mas nao encaminhe as rotas documentadas.

## Caminhos seguintes

1. Abrir chamado/suporte com APILIB usando o log do diagnostico e solicitar confirmacao do endpoint real para `Diario_Oficial - v1`.
2. Perguntar explicitamente se o gateway espera `Authorization: Bearer`, `apikey`, ou ambos.
3. Confirmar se a aplicacao esta assinada na API correta e no ambiente correto.
4. Manter o fallback publico em preparacao via:

```text
https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php?acao=materias_pesquisar
```

## Decisao Sprint 1B

Nao continuar com testes manuais avulsos no terminal. O caminho oficial passa a ser:

- executar `scripts/diagnose_doc_sp.py` para descoberta avancada e relatorio completo;
- usar `hermes/connectors/doc_sp/public_search.py` como base do fallback publico caso o gateway siga inacessivel.
