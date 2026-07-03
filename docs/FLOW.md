# Fluxo da plataforma

## Ciclo de coleta

```mermaid
sequenceDiagram
    participant Worker as scheduler worker
    participant Collector as collector
    participant Parser as parser
    participant Classifier as classifier
    participant Service as ingestion service
    participant DB as PostgreSQL

    Worker->>Collector: iniciar ciclo
    Collector-->>Worker: itens oficiais
    Worker->>Parser: parsear item
    Parser-->>Worker: publicacao normalizada
    Worker->>Classifier: classificar texto
    Classifier-->>Worker: tags e labels
    Worker->>Service: ingerir
    Service->>DB: buscar fonte/publicacao
    alt nova publicacao
        Service->>DB: inserir publicacao e versao 1
    else publicacao alterada
        Service->>DB: atualizar publicacao e criar nova versao
    else sem mudanca
        Service->>DB: atualizar data de coleta
    end
```

## Estados de coleta

- `running`: ciclo em andamento.
- `success`: ciclo finalizado sem erro.
- `failed`: ciclo interrompido com erro registrado.

## Deduplicacao

A ordem de identificacao e:

1. `source_id + external_id`, quando a API fornece identificador estavel.
2. `source_id + content_hash`, quando nao ha identificador externo.

O hash considera payload bruto e texto original para reduzir risco de colisao operacional.

## Classificacao

Na Fase 1, a classificacao por palavras-chave serve como adapter inicial e validacao de fluxo. A integracao com DeepSeek deve implementar a mesma interface `PublicationClassifier`, sem alterar ingestao, parser ou banco principal.

