# Decisoes tecnicas

## Python como base

Python foi escolhido pela maturidade do ecossistema para integracoes HTTP, processamento de texto, IA, agendamento e automacao operacional.

## FastAPI apenas operacional

FastAPI foi usado para `/health`, `/version` e futuro acesso programatico. A UI de documentacao automatica foi desabilitada para manter a premissa de nao criar interface grafica.

## API separada do worker

Coleta continua nao deve depender do processo HTTP. Por isso o Compose tem `api` e `worker` separados, ambos usando a mesma imagem.

## Migrator separado

O servico `migrator` aplica Alembic antes de `api` e `worker`. Isso evita que cada processo tente migrar o banco ao mesmo tempo.

## PostgreSQL com JSONB e colunas estruturadas

Campos importantes para consulta ficam em colunas proprias. Dados originais e informacoes especificas de cada API ficam em JSONB para preservar tudo sem travar a evolucao do schema.

## Versionamento de publicacoes

`publication_versions` foi criado desde a Fase 1 porque publicacoes oficiais podem mudar, ser retificadas, suspensas ou republicadas. O HERMES deve preservar historico, nao apenas o estado atual.

## Classificador desacoplado

O classificador atual por palavras-chave implementa o contrato `PublicationClassifier`. DeepSeek deve entrar como outro provider sem mudar o servico de ingestao.

## Logging estruturado

`structlog` em JSON facilita operacao em VPS, integracao com Docker logs e futura coleta por observabilidade.

## Sem dependencia local

O projeto local serve para desenvolvimento. A operacao alvo e Docker na VPS, com variaveis em `.env` e banco em volume persistente.

