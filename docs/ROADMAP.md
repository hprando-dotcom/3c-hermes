# Roadmap

## Fase 1 - Fundacao

- Estrutura modular.
- Docker e Compose.
- PostgreSQL e Alembic.
- Modelagem inicial.
- API operacional com `/health` e `/version`.
- Scheduler e collector preparados.
- Logging estruturado.
- Configuracao por `.env`.
- Documentacao inicial.

## Fase 2 - Primeiras fontes reais

- Implementar coletores para APIs publicas prioritarias.
- Normalizar campos por fonte.
- Registrar fontes no banco.
- Adicionar politicas de retry, backoff e rate limit.
- Criar testes de contrato para cada fonte.

## Fase 3 - Enriquecimento

- Download de PDFs e anexos.
- Extracao de texto.
- OCR quando necessario.
- Normalizacao de CNPJ, valores, datas e municipios.
- Melhor deduplicacao entre fontes.

## Fase 4 - IA desacoplada

- Adapter DeepSeek.
- Fila de classificacao.
- Prompts versionados.
- Auditoria de classificacoes.
- Reprocessamento controlado.

## Fase 5 - Escala operacional

- Particionamento de tabelas grandes.
- Storage externo para arquivos.
- Observabilidade com metricas.
- Backups e restore testado.
- Rotinas de manutencao de indices.

## Fase 6 - Consulta e produto de dados

- APIs de consulta sobre banco abastecido.
- Filtros por dominio, localidade, tipo, orgao, empresa e periodo.
- Exportacoes e relatorios.
- Autorizacao e limites por usuario, se necessario.

