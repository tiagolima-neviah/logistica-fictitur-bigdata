<a id="topo"></a>

# Entendimento do Negócio — Fictitur Logística

<!-- nav:start -->
[Home](../README.md) | [Entendimento dos Dados →](02_entendimento_dados.md)
<!-- nav:end -->

> Quem é a empresa fictícia deste caso, como ela opera, que dores motivaram o projeto e o que o pipeline entrega. Este documento é a porta de entrada: quem entende o negócio lê os dados com outros olhos.

## 1. A empresa

A **Fictitur Logística** é uma operadora logística de ponta a ponta. Da matriz em São Paulo, com **4 galpões** (GLP01 a GLP04), ela presta dois serviços principais a mais de **200 clientes** de segmentos variados (alimentício, cosméticos, eletrônicos, saúde, moda, químico):

- **Estoque e armazenagem:** o cliente envia mercadoria para os galpões da Fictitur, que recebe (mediante agendamento), endereça, guarda, inventaria e controla validade por lote. A cobrança é mensal, calculada sobre o volume ocupado (R$/m³) e o valor da mercadoria armazenada (ad valorem).
- **Entregas:** o cliente emite pedidos e a Fictitur separa, confere, expede e entrega em todo o Brasil, com frota parceira (transportadores contratados e parceiros de redespacho) e uma rede de **36 bases parceiras** distribuídas pelo país. A cobrança é por frete, sobre peso taxado (o maior entre peso real e peso cubado).

Serviços complementares completam a receita: coletas, montagem de kits, insumos de produção e positivação em lojas.

## 2. Como um pedido vive

O ciclo de vida do pedido é a espinha do negócio. Ele nasce numa solicitação (SS) via API, web ou grade programada; passa por pré-conferência, distribuição de cotas e planejamento; vira ordens de manuseio (separação, conferência); ganha nota fiscal; entra numa **minuta** (o romaneio que agrupa pedidos num veículo); é expedido; viaja; e termina na entrega ao destinatário, com prazo prometido ao cliente. Em cada etapa há um prazo interno (SLA de manuseio, que depende do horário de corte) e um prazo de transporte (que depende de UF, município e modalidade). Atrasos têm motivo registrado; devoluções e reentregas geram novos custos e novos fretes.

O indicador rei é o **OTIF** (On Time In Full): o percentual de pedidos entregues no prazo e completos. Cada cliente tem um OTIF contratual (tipicamente entre 90% e 98%); ficar abaixo custa multa e, pior, custa confiança.

## 3. A história nos números (2020 a 2026)

O universo sintético cobre **janeiro de 2020 a setembro de 2026** e conta uma história deliberada: em 2020 a operação ia mal, com OTIF geral entre 75% e 90% e clientes menores chegando a 50%, à beira do churn. De 2021 a 2023 os indicadores oscilaram sem tendência, o problema era crônico. Em 2024 uma troca na vice-presidência trouxe gestão profissional, e a partir do segundo semestre os indicadores viraram: em 2025 e 2026 a operação atinge 98% de OTIFs em faixa ótima, com melhora consistente em prazos, avarias, aging de estoque e margens. Quem analisar as camadas do pipeline vai encontrar essa curva; ela é o terreno de análises de antes e depois que um BI de verdade existe para responder.

## 4. As dores que motivaram o projeto

1. **Relatórios que não batem.** Cada relatório da empresa recorta e reagrega os dados por conta própria, e usuários mantinham planilhas paralelas cruzando relatórios extraídos do sistema. Resultado: dois números diferentes para a mesma pergunta, e reuniões discutindo qual planilha está certa em vez de discutir o negócio.
2. **Banco de produção sofrendo.** O banco de BI vive no mesmo servidor do sistema transacional, e as cargas pesadas de leitura concorrem com a operação, degradando os dois.

## 5. O que o projeto entrega

Um **staging** que espelha o banco relacional com carga incremental diária (a produção respira), e um pipeline analítico (bronze → silver → gold → star schema) que reconstrói todos os indicadores de **uma única fonte da verdade**: dimensões únicas, muitas fatos por tema, e o mesmo OTIF em qualquer relatório, por construção. No fim da esteira, datamarts por área alimentam dashboards web e Power BI. O BI aqui cumpre seu papel correto: comparar o histórico com o presente para decidir melhor, não vigiar a operação em tempo real (isso é papel do sistema operacional).

---

[Início](#topo)
