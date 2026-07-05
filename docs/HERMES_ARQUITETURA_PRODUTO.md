# HERMES - Arquitetura de Produto

## O que o HERMES e

O HERMES e um agente de inteligencia publica. Ele consulta fontes publicas em nome do usuario, interpreta dados governamentais e entrega achados, alertas e relatorios acionaveis.

Frase central:

> O HERMES nao e uma ferramenta para o usuario consultar dados publicos. O HERMES e um agente que consulta fontes publicas em nome do usuario, interpreta os dados e entrega achados, alertas e relatorios acionaveis.

## O que o HERMES nao e

O HERMES nao deve ser tratado como:

- um formulario de banco de dados;
- uma tela de filtros tecnicos;
- um catalogo de conectores;
- um painel que exige que o usuario saiba qual tabela consultar;
- um CRUD de publicacoes.

Filtros, tabelas, SQL, conectores e endpoints existem, mas sao bastidores. A experiencia principal e orientada por missoes.

## Arquitetura por camadas

### 1. Camada de Fontes

Fontes publicas monitoradas ou planejadas:

- PMSP Licitacoes;
- TCE-SP Transparencia Municipal;
- PNCP;
- Compras.gov;
- Diario Oficial;
- bases futuras de municipios, tribunais e portais de transparencia.

### 2. Camada de Ingestao

Responsavel por:

- conectores;
- parsers;
- normalizadores;
- persistencia;
- logs;
- diagnosticos;
- qualidade dos dados.

Essa camada deve ser robusta, auditavel e reutilizavel, mas nao deve dominar a experiencia visual do usuario.

### 3. Camada de Conhecimento

Transforma dados brutos em memoria operacional:

- orgaos;
- municipios;
- fornecedores;
- contratos;
- despesas;
- receitas;
- objetos;
- eventos;
- historico de publicacoes;
- evidencias preservadas.

### 4. Camada de Inteligencia

Interpreta uma missao e decide como investigar:

- identifica temas e intencoes;
- seleciona fontes;
- consulta dados persistidos;
- produz rankings;
- detecta recorrencias;
- aponta lacunas;
- gera alertas;
- monta resumo executivo;
- prepara relatorios.

No MVP, essa camada usa heuristicas locais. Ela foi desenhada para receber IA externa no futuro sem mudar a experiencia principal.

### 5. Camada de Experiencia

O usuario deve abrir o HERMES e encontrar:

- campo "O que voce quer que o HERMES investigue?";
- missoes sugeridas;
- relatorios;
- alertas;
- fontes monitoradas;
- status operacional;
- modo exploratorio avancado para PMSP e TCE-SP.

## Conceito de missao

Uma missao e uma solicitacao em linguagem natural. Exemplos:

- "Veja obras e manutencao em Sao Paulo."
- "Quais fornecedores aparecem mais em contratos de manutencao?"
- "Me traga um resumo das movimentacoes de saude."
- "Monitore Balsamo no TCE-SP."
- "Quais orgaos estao mais ativos?"

O HERMES deve transformar a missao em uma investigacao estruturada: bases consultadas, resumo executivo, achados, rankings, evidencias, alertas e proximas perguntas.

## Conceito de relatorio

Um relatorio e uma resposta organizada e reaproveitavel. No MVP, relatorios sao atalhos estaticos para investigacoes frequentes. No futuro, devem ser persistidos, versionados e agendaveis.

Relatorios iniciais:

- Resumo PMSP;
- Engenharia e manutencao PMSP;
- Fornecedores PMSP;
- Resumo TCE-SP.

## Conceito de alerta

Um alerta e uma condicao que merece atencao. Pode nascer de:

- recorrencia de fornecedor;
- concentracao de orgao;
- registros sem fornecedor;
- registros sem contrato;
- ausencia de dados esperados;
- crescimento de atividade em uma fonte.

No MVP, alertas aparecem como observacoes de qualidade e achados simples. No futuro, devem virar monitoramentos configuraveis.

## Papel das fontes

As fontes indicam de onde o HERMES obtem evidencia. Elas nao devem ser a primeira pergunta feita ao usuario. A pergunta inicial e a missao; a selecao de fontes e responsabilidade do agente.

## Papel dos conectores

Conectores sao infraestrutura. Eles devem:

- buscar dados;
- tratar erros;
- normalizar registros;
- preservar payload bruto;
- permitir diagnostico e repeticao.

Eles nao definem a experiencia principal.

## Papel da UI

A UI deve comunicar que o HERMES investiga. A home deve abrir com uma missao, nao com filtros de tabela. PMSP e TCE-SP continuam acessiveis como modo exploratorio avancado.

## Roadmap

### PMSP

- Manter ingestao e consulta avancada.
- Fortalecer missoes de obras, manutencao, saude, educacao, fornecedores e orgaos ativos.
- Evoluir relatorios e alertas.

### TCE-SP

- Manter ingestao por municipio/ano/mes.
- Usar despesas e receitas em missoes municipais.
- Adicionar monitoramento por municipio.
- Avaliar downloads Audesp/Fase IV de licitacoes e contratos em etapa controlada, sem baixar bases grandes automaticamente.

### PNCP

- Planejar conector e normalizacao.
- Integrar a camada de inteligencia para compras e contratos nacionais.

### Compras.gov

- Planejar descoberta e ingestao.
- Cruzar fornecedores e objetos com PMSP, TCE-SP e PNCP.

## Criterios de aceite do produto

- A home comunica que o HERMES e um agente de inteligencia publica.
- A experiencia principal comeca por uma missao em linguagem natural.
- O usuario consegue investigar "obras e manutencao em Sao Paulo".
- A resposta traz resumo executivo, bases consultadas, achados, rankings, evidencias, alertas e proximas perguntas.
- PMSP e TCE-SP continuam disponiveis como consultas avancadas.
- `/status`, `/docs`, `/openapi.json`, scripts e endpoints existentes continuam funcionando.
- Nenhuma dependencia de segredo e introduzida.
- O HERMES nao depende de Jarvis nem altera Jarvis.
