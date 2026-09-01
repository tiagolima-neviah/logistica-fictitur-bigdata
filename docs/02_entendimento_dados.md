<a id="topo"></a>

# Entendimento dos Dados — o banco relacional da Fictitur

<!-- nav:start -->
[Home](../README.md) | [← Entendimento do Negócio](01_entendimento_negocio.md) | [Modelo de Dados →](03_modelo_dados_staging.md)
<!-- nav:end -->

> O mapa do banco `db_fictitur`: 5 schemas e 50 tabelas que representam o ambiente relacional da empresa, espelhado no staging com carga incremental diária. O DDL completo e comentado está em [`staging/ddl/`](../staging/ddl/); este documento explica o papel de cada grupo de tabelas e as regras que os dados carregam.

## 1. Visão geral

| schema | papel | tabelas |
|---|---|---|
| `cadastro` | entidades mestres e parametrização | 20 |
| `fwm` | operação: pedidos, recebimento, estoque, serviços | 17 |
| `expedicao` | transporte: minutas, entregas, ocorrências, coletas | 6 |
| `faturamento` | receitas: faturas de frete, armazenagem e serviços | 3 |
| `financeiro` | custos, tarifas e parâmetros (base do BI de margens) | 4 |

O detalhamento técnico, com o diagrama do modelo e o objetivo de cada uma das 50 tabelas, está no [Modelo de Dados do Staging](03_modelo_dados_staging.md).

## 2. `cadastro` — quem é quem e as regras do jogo

O coração é a tabela `organizacao`, no padrão Party: uma única tabela para a **matriz**, as **36 bases parceiras** e os **203 clientes**, diferenciados por `tipo_parceria`, com porte, segmento e o OTIF contratual de cada cliente. `endereco` guarda sedes, destinos de entrega e galpões, ancorados na geografia real do Brasil (`uf`, `municipio`, `regiao`). O catálogo `item` pertence a cada cliente e carrega as dimensões físicas que o negócio usa o tempo todo (peso, medidas, múltiplo de saída, valor unitário). A infraestrutura física segue uma regra importante: **galpão é o local de armazenagem, pertence a uma organização (matriz ou base) e tem endereço próprio, um para um**. Uma organização pode ter zero ou vários galpões, e eles não precisam dividir o mesmo teto. Neste caso, a regra é simples: a **matriz** tem os quatro galpões (GLP01 a GLP04, que podem ocupar o mesmo complexo ou cidades vizinhas), e cada **base parceira é ela própria o seu único galpão**, no endereço da base. Abaixo do galpão vêm `doca` (recebimento) e `posicao_armazem` (endereçamento interno). Fecham o schema os agentes (`transportador`, `parceiro_redespacho`, `usuario`, `representante`) e as **regras parametrizadas**: `fase` (o catálogo das 10 fases do pedido, da Seção 3) com sua régua interna `sla_fase` em horas úteis, `sla_manuseio` (prazos por cliente, sensíveis ao horário de corte), `sla_transporte` (prazo por UF × município × modalidade) e `meta_frete` (metas de R$/kg por região e tipo de destino).

## 3. `fwm` — a operação acontecendo (Fictitur Warehouse Management)

Dois fluxos e três camadas de estoque:

- **Saída (pedidos):** `pedido` (chave natural SS) → `pedido_item` → `pedido_fase`, o histórico longo das fases: cada passagem registra entrada e saída, e a linha com saída em aberto é a fase atual. O ciclo tem **10 fases catalogadas** (`cadastro.fase`): EA Em Análise · PC Pré-Conferência · DC Distribuição de Cotas · PL Planejamento · EX Expedição · CF Coleta Física · ME Manuseio · EN Emissão de NF · EC Entrega ao Cliente · CE Coleta Externa, sendo DC e EX esporádicas (nem todo pedido passa por elas). `os` e `nf` amarram ordem de serviço e nota fiscal. As durações de cada fase **não são colunas**: derivam sempre dos timestamps, porque duração digitada envelhece e mente.
- **Entrada (recebimento):** `agendamento` (o fornecedor marca chegada num galpão e doca) → `ordem_recebimento` → `recebimento_item`, com `agendamento_ocorrencia` registrando os percalços.
- **Estoque em três camadas com papéis distintos:** `movimento_estoque` é o diário (toda entrada, saída, ajuste e transferência); `estoque_saldo` é a posição corrente por item × lote × posição; e `estoque_snapshot` é a **foto oficial que o sistema gera** (fechamento mensal mais a diária do mês corrente), base da cobrança de armazenagem, com volume ocupado e valor congelados na data da foto. `lote` carrega as validades; `inventario` e `inventario_item`, as contagens.

Serviços de valor agregado fecham o schema: `servico_complementar` (montagem de kits, insumos, com custo de material e de mão de obra) e `positivacao` (serviços em loja).

## 4. `expedicao` — da doca ao destinatário

`minuta` é o romaneio: agrupa pedidos (`minuta_pedido`) num veículo de um `transportador`, com tipo de carga consolidada ou exclusiva. `entrega` guarda os três prazos que o negócio compara (prometido ao cliente, interno e real previsto) e o desfecho: data de entrega, recebedor, canhoto. `ocorrencia_entrega` registra o que aconteceu no caminho (ocorrências, devoluções, reentregas, avarias), com `motivo_atraso` catalogado. `coleta` cobre o fluxo inverso: buscar mercadoria na origem.

## 5. `faturamento` e `financeiro` — receita, custo e margem

O `faturamento` registra as receitas: `fatura_frete` por pedido/OS (valor com e sem ICMS, peso faturado), `fatura_armazenagem` por cliente × competência e `fatura_servico` para coletas, positivações e serviços complementares.

O `financeiro` fecha a conta da **margem de contribuição**: `custo_operacao` lança os custos variáveis por operação (custo real do frete, coleta, insumos, mão de obra, DIFAL, devolução/reentrega); `tarifa_armazenagem` (R$/m³ + ad valorem + mínimo mensal por cliente) e `tarifa_frete` (preço teórico por cliente, modal, UF e faixa de peso) são as tabelas comerciais; e `parametro_financeiro` versiona por vigência os parâmetros de negócio: taxa de imposto sobre faturamento, fatores de cubagem (rodoviário e aéreo), custo do m³ de galpão, alíquotas de ICMS e DIFAL. A margem nunca é digitada: `MC = receita − impostos − custo variável`, calculada no pipeline a partir destas tabelas.

## 6. O que esperar da qualidade destes dados

O gerador sintético reproduz, de propósito e em taxa calibrada, a sujeira que um banco de produção real carrega: datas-sentinela herdadas de sistemas antigos, datas impossíveis no futuro, campos de processo massivamente nulos, agendamentos sem chegada, cancelamentos, itens com saldo e sem valor unitário. Há também denormalizações realistas documentadas no próprio DDL (descrições gravadas no momento da transação, geografia fotografada no pedido). Nada disso é acidente: é o terreno de treino do pipeline, e o tratamento de cada caso será documentado nas camadas silver e gold.

---

[Início](#topo)
