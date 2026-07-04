# Modelo do banco

## Diretrizes

- PostgreSQL e a fonte de verdade.
- Chaves primarias de tabelas volumosas usam `BIGINT IDENTITY`.
- Dados originais sao preservados em `JSONB` e `TEXT`.
- Mudancas em publicacoes sao registradas em `publication_versions`.
- Campos estruturados comuns ficam em colunas proprias para consultas e indices.

## Tabelas

### `sources`

Cadastro das fontes oficiais monitoradas. Guarda codigo, nome, API, URL base, escopo e metadados.

### `collection_runs`

Historico de execucoes de coleta. Guarda status, inicio, fim, quantidade encontrada, inserida, atualizada e erro.

### `publications`

Tabela principal de publicacoes. Armazena orgao, ente, UF, municipio, fonte, tipo, objeto, modalidade, situacao, numero, ano, valores, prazos, links, payload bruto, payload normalizado, texto original, texto limpo, classificacao, tags, palavras-chave, hash, versao e timestamps.

### `publication_versions`

Historico de versoes por publicacao. Sempre que o hash muda, uma nova versao e gravada com payload, textos, classificacao e campos alterados.

### `publication_companies`

Empresas relacionadas a uma publicacao. Permite registrar vencedora, contratada, participante ou outro papel.

### `publication_files`

Arquivos associados, como PDFs, anexos e documentos oficiais. A Fase 1 guarda URL e metadados; o armazenamento fisico pode ser adicionado depois.

### `classification_results`

Resultados historicos de classificacao. Mantem provider, modelo, labels, tags, palavras-chave e confianca.

### `pmsp_licitacoes`

Tabela dedicada para registros normalizados da API PMSP Licitacoes/Dados Abertos CKAN. Guarda fonte efetiva, sistema de origem, ano, orgao, modalidade, numeros de licitacao/processo/contrato, objeto, fornecedor, documento do fornecedor, valor, datas, evento, retranca, hash de origem, payload bruto em `raw_json` e timestamps.

O campo `source_hash` e unico e sustenta o upsert, evitando duplicacao logica entre execucoes de ingestao.

### `tcesp_municipios`

Tabela dedicada aos municipios retornados pela API publica do TCE-SP. Guarda slug oficial, nome extenso, payload bruto em `raw_json` e timestamps.

### `tcesp_despesas`

Tabela operacional para despesas municipais TCE-SP por municipio, exercicio e mes. Guarda orgao, evento, numero de empenho, fornecedor, data de emissao, valor, fonte e payload bruto.

### `tcesp_receitas`

Tabela operacional para receitas municipais TCE-SP por municipio, exercicio e mes. Guarda orgao, fonte de recurso, aplicacao, alinea, subalinea, valor arrecadado, fonte e payload bruto.

## Indices iniciais

- Fonte e identificador externo.
- Hash de conteudo.
- UF e municipio.
- Data de publicacao.
- Tipo de publicacao.
- `GIN` para tags, palavras-chave e JSONB.
- `pg_trgm` para objeto e texto limpo.
- `pmsp_licitacoes`: indices em `ano`, `orgao`, `numero_processo`, `numero_contrato` e unicidade em `source_hash`.
- `tcesp_municipios`: unicidade em `municipio_slug` e indice em `municipio_extenso`.
- `tcesp_despesas`: indices em municipio/exercicio/mes, fornecedor e orgao.
- `tcesp_receitas`: indices em municipio/exercicio/mes, orgao e fonte de recurso.

## Evolucao recomendada

- Particionar `publications` e `publication_versions` por mes ou trimestre quando o volume justificar.
- Criar tabelas auxiliares para orgaos e municipios se as consultas exigirem dimensoes normalizadas.
- Separar armazenamento de arquivos em bucket/S3 compativel.
- Adicionar filas para parsing pesado, OCR e classificacao por IA.
