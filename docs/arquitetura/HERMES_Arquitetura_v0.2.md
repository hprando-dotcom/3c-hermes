# HERMES - Arquitetura v0.2

## Status

Documento de arquitetura formal da versao v0.2 do HERMES.

Esta versao consolida a visao fundadora documentada em
[`docs/HERMES_ARQUITETURA_PRODUTO.md`](../HERMES_ARQUITETURA_PRODUTO.md)
e incorpora as decisoes tomadas apos o teste real do DOE-TCESP.

Documento relacionado:
[`ADR-0001 - Evidencia-First e Operacao Diaria Programada`](../decisoes/ADR-0001-evidencia-first-operacao-diaria.md).

## Limites do projeto

HERMES e o projeto de rastreamento de publicacoes oficiais.
HERMES nao e Jarvis.
HERMES nao depende do Jarvis.
HERMES nao altera Jarvis.
O ambiente de referencia do HERMES na VPS e `/opt/hermes`.
O caminho `/opt/jarvis` esta fora do escopo do HERMES.

Esta arquitetura e apenas documental. Ela nao cria banco, migration, rotina
Docker, segredo, chave, endpoint ou codigo de aplicacao.

## Tese central

O HERMES nao e buscador.
O HERMES nao e robo de consultas.
O HERMES e um organismo permanente de coleta de conhecimento.

APIs nao sao o produto.
APIs alimentam o produto.

O banco bruto preserva a prova.
O banco inteligente organiza o conhecimento.

O usuario nao deve precisar escolher tabela, endpoint, conector ou filtro
tecnico como primeira acao. A experiencia principal comeca por uma missao em
linguagem natural, e o HERMES decide quais fontes oficiais consultar, como
coletar evidencia, como classificar e como entregar o resultado operacional.

## Principio v0.2: Evidencia-First

A v0.2 deixa de tratar a investigacao como scraping generico orientado por
links e passa a tratar a investigacao como coleta oficial orientada por
evidencia.

Fluxo correto:

```text
Missao
-> identificar tipo de fonte
-> usar conector especifico
-> baixar documento oficial/API/PDF/HTML
-> salvar bruto
-> extrair texto
-> procurar termos/processos/orgaos/empresas
-> validar evidencia
-> classificar com IA
-> salvar no banco inteligente
-> gerar relatorio/Excel/alerta
```

A coleta e a preservacao do documento oficial vem antes da IA.
A classificacao vem depois da evidencia.

## Regra de achado valido

Regra de ouro:

> Achado valido tem que vir de fonte oficial cadastrada. Sempre.

Um achado valido no HERMES e qualquer publicacao, documento, ato, decisao,
edital, contrato, aviso, acordao, extrato, resultado, homologacao, aditivo ou
movimentacao oficial que:

1. venha de fonte oficial cadastrada;
2. tenha evidencia auditavel;
3. esteja relacionado a uma missao, palavra-chave, processo, orgao, empresa,
   objeto ou categoria monitorada;
4. possua link, documento, pagina, trecho ou registro bruto salvo;
5. possa ser consultado novamente no banco bruto do HERMES, mesmo que a fonte
   original saia do ar;
6. respeite a regra de ouro: o HERMES so reconhece achado quando a origem for
   oficial, nunca homepage generica, midia social, link lateral, pagina
   institucional sem publicacao ou conteudo sem valor probatorio.

Regra negativa:

Nao e achado valido:

- homepage;
- menu de site;
- pagina institucional generica;
- YouTube;
- pagina de audio/video, salvo se a missao for especificamente sobre midia;
- link sem trecho relevante;
- resultado sem documento oficial;
- classificacao feita so por IA sem evidencia;
- pagina que apenas contem palavras genericas como "Tribunal", "licitacao" ou
  "publicacoes".

Frase definitiva:

> Sem fonte oficial e sem evidencia oficial auditavel, nao existe achado.

## Fontes iniciais

### PNCP

O PNCP e fonte prioritaria para licitacoes.

Na fase inicial:

- usar API oficial;
- pesquisar apenas licitacoes estaduais;
- nao incluir licitacoes municipais;
- aplicar filtros deterministicos antes de qualquer chamada de IA;
- priorizar objetos de engenharia, infraestrutura e construcao civil.

Municipios serao monitorados inicialmente pelos diarios oficiais municipais
escolhidos, nao por varredura municipal ampla do PNCP.

### Diarios e fontes oficiais

Carteira inicial de fontes:

| Fonte | URL |
| --- | --- |
| DOE-SP | https://doe.sp.gov.br/ |
| Diario Oficial da Prefeitura de Sao Paulo | https://diariooficial.prefeitura.sp.gov.br/ |
| Guarulhos | https://www.guarulhos.sp.gov.br/diario-oficial |
| Osasco | https://osasco.sp.gov.br/ |
| Diadema | https://www.diadema.sp.gov.br/diario-oficial |
| Sao Jose dos Campos | https://www.sjc.sp.gov.br/servicos/governanca/boletim-oficial/ |
| Taubate | https://www.taubate.sp.gov.br/diariooficial/ |
| DOE-TCESP | https://doe.tce.sp.gov.br/ |
| Minas Gerais | https://diarioweb.mg.gov.br/ |
| Espirito Santo | https://dio.es.gov.br/diario-oficial |
| Parana | https://www.documentos.dioe.pr.gov.br/dioe/localizar.do |
| Santa Catarina | https://portal.doe.sea.sc.gov.br/ |
| Rio Grande do Sul | https://www.diariooficial.rs.gov.br/ |

### Regra de fase inicial

Nem todas as fontes serao raspadas diariamente desde o inicio.

Rodar diariamente no inicio:

- Diario Oficial da cidade de Sao Paulo / PMSP;
- Diario Oficial do Estado de Sao Paulo / DOE-SP;
- DOE-TCESP.

Demais fontes:

- ficam cadastradas como carteira inicial;
- podem rodar sob demanda;
- podem rodar semanalmente;
- podem entrar por fase;
- podem rodar quando houver missao especifica.

## Estrategia de investigacao por fonte

### PNCP

O PNCP deve ser tratado como fonte estruturada com API oficial.

Diretrizes:

- usar filtro pesado antes da IA;
- restringir a fase inicial a licitacoes estaduais;
- filtrar por UF, orgao, modalidade, status, data, objeto e palavras-chave;
- priorizar termos de engenharia, infraestrutura e construcao civil;
- nao enviar todo o PNCP para IA;
- chamar IA apenas depois de filtros deterministicos e preservacao do bruto.

### DOE-TCESP

O DOE-TCESP exige estrategia propria.

E uma fonte especialmente relevante para:

- processos TC;
- acordaos;
- decisoes;
- representacoes;
- sustacoes cautelares;
- exames previos de edital.

Diretrizes:

- buscar processos, partes, empresas, orgaos e palavras-chave especificas;
- sempre que possivel, usar PDF diario;
- preservar pagina, trecho, edicao, data de disponibilizacao, data de
  publicacao legal e link direto com `#page`;
- registrar o documento bruto antes de classificar;
- nunca aceitar uma pagina generica do site como achado juridico.

### DOE-SP e PMSP

DOE-SP e PMSP podem exigir combinacao de scraping, busca interna, endpoint
descoberto, PDF, HTML ou navegador headless quando necessario.

Diretrizes:

- preservar sempre a fonte oficial;
- preservar evidencia auditavel;
- guardar bruto antes de extrair ou classificar;
- registrar falhas, lacunas e comportamento da fonte no log de varredura;
- evitar conclusao positiva quando houver apenas navegacao ou link lateral sem
  publicacao oficial.

## Banco bruto

Banco bruto e prova oficial preservada.

Guardar:

- documento original PDF/HTML/JSON/API;
- texto integral extraido;
- fonte oficial;
- URL original;
- link da publicacao;
- data de coleta;
- data de publicacao;
- data de disponibilizacao, quando houver;
- pagina do PDF, quando houver;
- hash do documento;
- metadados minimos;
- registro de origem.

Regras:

- o banco bruto deve ser acumulado, permanente e auditavel;
- o banco bruto nao deve ser sobrescrito;
- o banco bruto nao deve depender de nova consulta a fonte original;
- o banco bruto deve permitir reprocessamento futuro;
- o banco bruto deve permitir extrair informacoes complementares depois.

Banco bruto = prova.

## Banco inteligente

Banco inteligente e conhecimento extraido, classificado, normalizado,
relacionado e consultavel.

Guardar entidades e relacionamentos:

- orgaos;
- contratantes;
- empresas;
- CNPJs;
- consorcios;
- licitacoes;
- editais;
- contratos;
- aditivos;
- apostilamentos;
- processos;
- acordaos;
- decisoes;
- eventos;
- objetos;
- valores;
- datas;
- municipios;
- estados;
- fontes;
- documentos;
- pessoas, relatores, fiscais e responsaveis;
- tipo de obra;
- categoria;
- prioridade;
- relevancia;
- alertas.

Cada dado inteligente deve estar vinculado ao bruto:

- documento bruto de origem;
- fonte oficial;
- link oficial;
- pagina;
- trecho;
- data de extracao;
- metodo/modelo usado;
- versao da regra/prompt;
- grau de confianca.

Banco inteligente = conhecimento operacional.

O banco inteligente pode ser reconstruido a partir do bruto. O bruto nao pode
ser descartado.

## Relatorio diario

O entregavel principal para o usuario e o Excel diario.

Formato:

```text
HERMES_Diario_YYYY-MM-DD.xlsx
```

Abas obrigatorias:

1. Licitacoes
2. Alteracoes Contratuais
3. Juridico
4. Log da Varredura

### Aba Licitacoes

Campos minimos:

- data da publicacao;
- fonte;
- orgao/contratante;
- estado/municipio;
- modalidade;
- numero da licitacao/edital;
- numero do processo;
- objeto;
- tipo de obra;
- regime de execucao;
- data de abertura;
- valor estimado, se houver;
- status;
- prioridade;
- link da fonte oficial;
- pagina/trecho de evidencia.

### Aba Alteracoes Contratuais

Campos minimos:

- data da publicacao;
- fonte;
- contratante;
- empresa contratada;
- CNPJ;
- numero do contrato;
- numero do processo;
- objeto do contrato;
- tipo de contrato;
- valor original;
- valor atual;
- tipo de alteracao;
- valor da alteracao, quando houver;
- nova data/novo prazo, quando houver;
- numero do aditivo/apostilamento;
- motivo/resumo;
- link da fonte oficial;
- pagina/trecho de evidencia.

### Aba Juridico

Campos minimos:

- data da publicacao;
- fonte;
- tribunal/orgao julgador;
- processo;
- relator;
- representante;
- representado;
- orgao envolvido;
- objeto;
- tipo de decisao;
- resultado;
- determinacao/efeito pratico;
- sessao;
- data de disponibilizacao;
- data de publicacao legal;
- pagina;
- link da fonte oficial;
- trecho de evidencia;
- prioridade.

### Aba Log da Varredura

Campos minimos:

- fonte analisada;
- data/hora de execucao;
- status;
- documentos coletados;
- achados validos;
- falhas;
- observacoes;
- tempo de execucao.

### Regra mensal

- gerar Excel mensal acumulado;
- enviar por e-mail ao usuario;
- depois de confirmado o envio/consolidacao, pode apagar arquivos derivados
  diarios para economizar espaco.

Nunca apagar:

- banco bruto;
- documentos oficiais;
- evidencias;
- textos extraidos;
- hashes;
- registros necessarios a rastreabilidade;
- consolidados mensais.

### JSON, CSV, ZIP e HTML

JSON, CSV, ZIP e HTML nao sao obrigatorios como entrega diaria principal.

Eles podem existir como:

- uso tecnico interno;
- painel;
- API;
- dossie sob demanda.

O usuario final tera Excel como entrega principal.

## Papel da IA

Papel da IA:

> Classificar informacao.

A IA deve ler o prompt/contexto operacional e, a partir dele, entender o que
fazer com a informacao coletada.

Sem prompt e sem contexto, a IA e burra.

Regra:

> IA nao cria achado. IA interpreta evidencia.

A IA deve atuar apos a coleta e preservacao do documento oficial.

Responsabilidades:

- classificar se e Licitacao, Alteracao Contratual ou Juridico;
- identificar tipo de obra;
- extrair campos quando o texto nao estiver estruturado;
- resumir publicacao;
- avaliar relevancia;
- relacionar orgao, empresa, contrato, edital e processo;
- sugerir prioridade;
- produzir resumo executivo quando necessario.

A IA nao substitui documento oficial.
A IA nao pode classificar homepage, midia social, menu ou pagina institucional
generica como achado.

## Investigacao manual

A investigacao manual tem dois tipos.

### Pesquisa pontual

O usuario pede uma investigacao agora.

Exemplos:

- "Procure a publicacao do acordao dos processos TC-..."
- "Pesquise licitacoes de contencao em Guarulhos nos ultimos 15 dias."
- "Verifique se saiu algo sobre a Concorrencia 90.065/2024 do DER."

### Ordem manual que vira missao recorrente

O usuario da uma ordem permanente.

Exemplos:

- "A partir de hoje, tudo que sair sobre a empresa XXX no TCE-SP, eu quero saber."
- "Tudo que sair de registro de preco de obras de drenagem ou obras de
  contencao, eu quero saber."

O HERMES deve transformar essas ordens em missoes/skills salvas no cerebro
operacional.

Cada missao aprendida deve guardar:

- nome;
- descricao;
- fontes oficiais;
- palavras-chave;
- empresas;
- CNPJs;
- orgaos;
- processos;
- tipo de publicacao;
- categoria: Licitacoes / Alteracoes Contratuais / Juridico;
- frequencia;
- status ativo/inativo;
- data de criacao;
- historico de execucoes;
- ultimos achados;
- formato de alerta.

O painel devera futuramente permitir:

- ver missoes ativas;
- ver missoes pausadas;
- editar missao;
- pausar;
- excluir;
- rodar agora;
- ver ultima execucao;
- ver ultimos achados.

Frase:

> Monitoramento diario e a rotina. Investigacao manual e a lupa. Missao
> aprendida e o cerebro operacional.

## Escopo setorial prioritario

A v0.2 orienta o HERMES prioritariamente para:

- engenharia;
- infraestrutura;
- construcao civil;
- obras publicas;
- servicos tecnicos de engenharia;
- manutencao;
- conservacao;
- pavimentacao;
- drenagem;
- contencao;
- saneamento;
- rodovias;
- pontes;
- viadutos;
- projetos;
- supervisao;
- fiscalizacao;
- gerenciamento;
- locacao de equipamentos pesados.

## Etapa futura: HERMES Knowledge Vault

Obsidian nao deve ser instalado como nucleo do HERMES.

Como etapa futura, o HERMES podera gerar uma pasta/vault Markdown compativel
com Obsidian, com notas e links internos para:

- orgaos;
- empresas;
- processos;
- contratos;
- editais;
- publicacoes;
- decisoes;
- fontes;
- relatorios.

Essa camada sera complementar:

- banco bruto = prova;
- banco inteligente = conhecimento estruturado;
- Excel = entrega operacional;
- Obsidian/Knowledge Vault = cerebro navegavel/grafo de conhecimento.

## Criterios de aceitacao da arquitetura v0.2

- achado valido exige fonte oficial cadastrada;
- achado valido exige evidencia oficial auditavel;
- documentos oficiais sao preservados no banco bruto antes da classificacao;
- IA classifica evidencia, nao cria achado;
- conectores por fonte substituem scraping generico como nucleo operacional;
- PNCP usa API oficial e filtro estadual inicial;
- DOE-TCESP tem estrategia propria;
- Excel diario e a entrega operacional principal;
- banco bruto e permanente;
- banco inteligente e reconstruivel;
- investigacao manual pode gerar missao recorrente;
- HERMES segue independente do Jarvis.
