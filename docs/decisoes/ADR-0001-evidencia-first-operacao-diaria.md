# ADR-0001 - Evidencia-First e Operacao Diaria Programada

## Status

Aceita.

## Contexto

O teste real com DOE-TCESP mostrou que o fluxo anterior, baseado em scraper
generico por links, podia gerar falsos positivos e deixar de localizar o PDF
oficial relevante.

O HERMES chegou a gerar relatorio visualmente organizado, mas sem evidencia
util suficiente para sustentar um achado valido. Isso contraria a tese central
do produto: o HERMES deve preservar prova oficial e transformar essa prova em
conhecimento operacional.

Documento arquitetural relacionado:
[`HERMES - Arquitetura v0.2`](../arquitetura/HERMES_Arquitetura_v0.2.md).

Base conceitual anterior:
[`HERMES - Arquitetura de Produto`](../HERMES_ARQUITETURA_PRODUTO.md).

## Problema

O HERMES estava correndo o risco de entregar relatorio bonito sem evidencia
util.

Esse problema se manifesta quando:

- uma homepage e tratada como achado;
- um menu de site e tratado como publicacao;
- uma pagina generica aparece porque contem palavras como "Tribunal" ou
  "publicacoes";
- um link lateral e aceito sem trecho relevante;
- a IA classifica conteudo sem documento oficial preservado;
- o sistema nao consegue consultar novamente o bruto depois da execucao;
- a fonte original sai do ar e o HERMES nao tem prova preservada.

Sem evidencia oficial auditavel, nao existe achado.

## Alternativas consideradas

### 1. Continuar com scraping generico

Vantagens:

- implementacao inicial mais simples;
- reaproveitamento de fluxo existente;
- menos conectores especificos no curto prazo.

Desvantagens:

- alto risco de falso positivo;
- baixa rastreabilidade;
- dificuldade para capturar PDFs oficiais;
- dificuldade para diferenciar homepage, menu, link lateral e publicacao real;
- pouca confianca operacional no relatorio final.

### 2. Usar apenas IA/navegador

Vantagens:

- flexibilidade de navegacao;
- capacidade de lidar com fontes diferentes sem modelagem inicial profunda.

Desvantagens:

- custo e variabilidade maiores;
- pouca auditabilidade se o bruto nao for salvo antes;
- risco de a IA criar conclusao sem evidencia suficiente;
- dependencia excessiva de prompt, contexto e estado de navegacao;
- dificuldade para reprocessamento historico.

### 3. Migrar para arquitetura Evidencia-First com conectores por fonte

Vantagens:

- preserva prova oficial;
- reduz ruido;
- reduz falso positivo;
- permite auditoria;
- permite reprocessamento;
- cria historico permanente;
- subordina IA a evidencia;
- sustenta relatorios operacionais confiaveis.

Desvantagens:

- exige conectores especificos por fonte;
- exige maior disciplina de modelagem;
- exige banco bruto obrigatorio;
- exige log de execucao mais rigoroso;
- aumenta o trabalho inicial antes de escalar novas fontes.

## Decisao

Adotar Evidencia-First como principio arquitetural da v0.2.

Operacao diaria programada passa a ser o nucleo do HERMES.
Investigacao manual passa a ser a lupa.
Missoes aprendidas passam a formar o cerebro operacional.

Fluxo decidido:

```text
Missao
-> fonte oficial cadastrada
-> conector especifico
-> documento oficial/API/PDF/HTML
-> banco bruto
-> extracao de texto
-> validacao de evidencia
-> classificacao por IA ou regra
-> banco inteligente
-> Excel diario/alerta/relatorio
```

## Motivos

A decisao foi tomada pelos seguintes motivos:

- rastreabilidade;
- prova oficial preservada;
- menor ruido;
- menos falso positivo;
- reprocessamento futuro;
- historico permanente;
- independencia em relacao a disponibilidade futura da fonte original;
- separacao clara entre prova bruta e conhecimento operacional;
- capacidade de auditar o motivo de cada achado;
- menor risco de a IA inventar relevancia sem documento oficial.

## Consequencias

Consequencias esperadas:

- maior necessidade de conectores especificos;
- maior robustez na coleta;
- banco bruto obrigatorio;
- IA subordinada a evidencia;
- banco inteligente reconstruivel a partir do bruto;
- relatorios em Excel como entrega operacional principal;
- PNCP com filtro estadual inicial;
- DOE-TCESP com estrategia propria;
- logs de varredura mais importantes para explicar falhas e lacunas;
- menos fontes rodando diariamente no inicio, com expansao por fase.

## Regras arquiteturais

- sem evidencia oficial auditavel = sem achado;
- IA interpreta evidencia, nao cria achado;
- banco bruto e imutavel no sentido operacional: acumula prova e nao deve ser
  sobrescrito;
- banco inteligente e reconstruivel;
- Excel diario e entrega operacional;
- fonte oficial cadastrada e requisito de validade;
- homepage, menu, midia social, link lateral e pagina institucional generica
  nao sao achado;
- PNCP usa API oficial e filtro deterministico antes de IA;
- na fase inicial, PNCP monitora licitacoes estaduais, nao municipais;
- diarios municipais escolhidos cobrem a camada municipal inicial;
- HERMES permanece independente do Jarvis.

## Impacto na operacao diaria

Rodar diariamente no inicio:

- Diario Oficial da cidade de Sao Paulo / PMSP;
- Diario Oficial do Estado de Sao Paulo / DOE-SP;
- DOE-TCESP.

Demais fontes ficam como carteira inicial e podem rodar:

- sob demanda;
- semanalmente;
- por fase;
- quando houver missao especifica.

## Impacto na investigacao manual

Pesquisa pontual continua permitida, mas deve obedecer a mesma regra:
primeiro fonte oficial e evidencia, depois classificacao.

Ordem manual recorrente deve virar missao aprendida, com:

- fontes oficiais;
- palavras-chave;
- empresas;
- CNPJs;
- orgaos;
- processos;
- categoria;
- frequencia;
- historico de execucoes;
- ultimos achados;
- formato de alerta.

## Validacao

Esta ADR nao altera codigo, banco, migrations, Docker, secrets ou arquivos do
Jarvis.

A validacao operacional desta mudanca documental deve verificar:

- os documentos de arquitetura e ADR existem;
- os links internos apontam para arquivos existentes;
- `git diff --stat` mostra apenas documentacao esperada desta tarefa;
- `git status` evidencia que nao houve alteracao em codigo, banco, migrations,
  Docker ou secrets por esta ADR.
