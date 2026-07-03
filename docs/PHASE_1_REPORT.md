# Relatorio da Fase 1

## Entrega

A Fase 1 criou uma fundacao operacional para o HERMES, preparada para evoluir durante anos sem misturar responsabilidades. O projeto foi estruturado como backend modular, conteinerizado, sem interface grafica e sem CRUD tradicional.

## Decisoes arquitetonicas

### Execucao em containers

Docker Compose define quatro servicos: `postgres`, `migrator`, `api` e `worker`. Essa separacao permite operar a plataforma na VPS com banco persistente, migracoes controladas, API operacional minima e coleta continua em processo independente.

### Banco como nucleo da plataforma

PostgreSQL foi modelado para guardar tanto campos estruturados quanto dados brutos. Essa escolha atende a regra de nunca perder informacao: cada publicacao pode manter payload original, texto original, texto limpo, JSON normalizado, classificacao, tags, links e historico de versoes.

### Schema inicial expansivel

Foram criadas tabelas para fontes, execucoes de coleta, publicacoes, versoes, empresas, arquivos e resultados de classificacao. A modelagem evita fechar cedo demais os formatos das APIs publicas, mas cria colunas para os campos que serao consultados com frequencia.

### Indices desde o inicio

A migracao inicial inclui indices por fonte, identificador externo, hash, localidade, data, tipo, tags, palavras-chave, JSONB e texto com `pg_trgm`. Isso prepara a base para crescimento e consultas historicas.

### Preservacao historica

Quando uma publicacao muda, o desenho previsto e atualizar o registro principal e gravar uma nova linha em `publication_versions`. Assim, o HERMES mantem o estado atual sem apagar evidencias anteriores.

### Scheduler separado

O scheduler roda no `worker`, nao dentro da API. Isso reduz acoplamento, facilita restart independente e prepara o projeto para coleta 24/7.

### Collector preparado

O modulo `collector` possui contrato abstrato, contexto de coleta e registro de coletores. A Fase 1 nao implementa fontes reais por decisao de escopo; a proxima fase deve adicionar coletores oficiais concretos.

### Parser e classifier desacoplados

O parser inicial preserva e limpa texto sem impor normalizacao prematura. O classificador inicial por palavras-chave valida o fluxo e prepara a integracao futura com DeepSeek por meio de interface propria.

### Configuracao por ambiente

Toda configuracao relevante entra por `.env`, incluindo banco, API, logging, scheduler, intervalo de coleta e parametros de IA futura.

### API minima

Foram criados apenas `/health` e `/version`. O endpoint `/health` verifica conectividade com o banco; `/version` informa metadados operacionais. A documentacao visual do FastAPI foi desligada.

## O que ficou pronto

- Estrutura completa do projeto.
- Dockerfile.
- Docker Compose.
- `requirements.txt`.
- PostgreSQL com Alembic.
- Modelos SQLAlchemy.
- Migracao inicial.
- API operacional.
- Worker com APScheduler.
- Collector, parser e classifier preparados.
- Logging estruturado.
- `.env.example`.
- Documentacao completa da Fase 1.

## Proximos passos recomendados

1. Escolher as primeiras APIs oficiais a integrar.
2. Implementar o primeiro collector real com testes de contrato.
3. Definir estrategia de rate limit e retry por fonte.
4. Adicionar pipeline de download de PDFs.
5. Validar volume e decidir quando particionar tabelas.

