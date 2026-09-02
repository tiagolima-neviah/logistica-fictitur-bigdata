<a id="topo"></a>

# Matriz de Barramento — dos indicadores ao star schema

<!-- nav:start -->
[Home](../README.md) | [← Camada Silver](08_camada_silver.md) | [Camada Gold →](10_camada_gold.md)
<!-- nav:end -->

> O projeto dimensional da gold, feito do jeito Kimball: partimos dos **relatórios que o negócio consome** (os indicadores e os filtros que eles exigem), declaramos o **grão** de cada fato, escolhemos as **dimensões conformadas** e cruzamos tudo na **matriz de barramento**. Dois painéis-alvo abrem a série: **Gestão de Materiais** e **Margens por Operação**. Este documento é o contrato da gold: aprovado, vira fatos e dimensões; nada se constrói fora dele.

## 1. Método (e uma decisão de arquitetura)

Levantamos, para cada painel, indicador por indicador: o que mede, em que grão, que filtros aceita. Um padrão apareceu no primeiro painel e virou regra: de cerca de 160 medidas, **apenas ~40 são medidas-base**; o resto é **camada de apresentação** (variação contra o período anterior, participação percentual, rankings, comparativos ano contra ano). Decisão: **a gold entrega as medidas-base no grão correto; a inteligência temporal e visual fica na ferramenta de apresentação** (DAX no Power BI, consultas no dashboard web). Fato que carrega "% de evolução" está fazendo o trabalho errado no lugar errado.

## 2. Painel 1 · Gestão de Materiais

O painel enxerga a operação de armazenagem ponta a ponta: o que entra, o que está parado, o que sai, o que se entrega, o que custa. Nove temas, cada um com sua fato:

| tema | indicadores-base | grão da fato | fato |
|---|---|---|---|
| Estoque (foto) | valor em estoque, saldo em unidades, m³ ocupado, custo de armazenagem (mês e acumulado), dias sem movimento (DSM) médio, itens sem movimentação, cobertura fiscal (% de SKUs com valor), avarias (qtde e valor) | foto mensal × item × galpão | `ft_estoque_foto` |
| Recebimento | tempo de recebimento, tempo de disponibilização de cota, pedidos recebidos, m³ recebida | item recebido por ordem de recebimento | `ft_recebimento` |
| Agendamentos e fornecedores | agendamentos, valor recebido, ocorrências de agendamento, no-show, desempenho por fornecedor | agendamento | `ft_agendamento` |
| Saída e manuseio | quantidade saída, tempo de manuseio (pedido → fim do manuseio), tempo de retirada | item de pedido expedido | `ft_saida` |
| Entregas e tracking | pedidos, entregues no prazo / fora do prazo, **OTIF**, ocorrências, reentregas, devoluções, valor de material distribuído, valor de NF, pedidos entregues | **item de pedido** (contagens de pedido por contagem distinta) | `ft_tracking` |
| Frete | fretes (SS), faturamento de frete, peso faturado, R$/kg realizado × meta por região e tipo de destino, faixas de peso, valor e quantidade de material | fatura de frete (SS) | `ft_frete` |
| Validade | quantidade e valor de estoque vencido, lotes a vencer por faixa | lote × item | `ft_validade` |
| Inventário | inventários, status (realizado / em andamento / não iniciado) | inventário | `ft_inventario` |

**Filtros do painel (as dimensões):** período (com comparativo ano anterior / mês anterior, que é apresentação), cliente, base/galpão, item (grupo, subgrupo, marca), UF e região, modalidade/modal, faixa de peso, fornecedor, transportador.

## 3. Painel 2 · Margens por Operação

O painel financeiro reconstrói a margem de contribuição de cada operação faturada e a decompõe por tipo de serviço, cliente, modal, veículo e UF, com o mês como eixo.

| tema | indicadores-base | grão da fato | fato |
|---|---|---|---|
| Margem por operação | receita, imposto sobre faturamento, ICMS, impostos totais, custo variável, custos + impostos, **MC (R$ e %)**, ticket, peso, volume, m³, valor de NF | operação faturada: tipo × cliente × SS/OS × competência | `ft_mc_operacao` |
| Cobrança de armazenagem | m³ médio, valor de material médio, valor calculado pela tarifa, valor cobrado, **diferença** (vazamento de cobrança), custo do m³ | cliente × competência | `ft_armazenagem_cobranca` |

**Filtros do painel:** competência, tipo de operação, cliente, modal, tipo de veículo, UF/cidade de destino.

## 4. Dimensões conformadas

As nove já construídas no G1 atendem a maior parte dos filtros: `dim_data`, `dim_cliente`, `dim_item`, `dim_geografia`, `dim_galpao`, `dim_modalidade`, `dim_fase`, `dim_transportador`, `dim_motivo_atraso`. O levantamento pede **cinco novas**:

| dimensão nova | por quê |
|---|---|
| `dim_tipo_operacao` | eixo principal do painel 2 (transporte, armazenagem, coleta, serviços) |
| `dim_veiculo` | tipo de veículo da minuta (fiorino, VUC, toco, truck, carreta), filtro dos dois painéis |
| `dim_faixa_peso` | as faixas de peso (a "máscara") que classificam fretes e explicam R$/kg |
| `dim_fornecedor` | fornecedores dos agendamentos (hoje texto livre na fato) |
| `dim_meta_frete` | metas de R$/kg por região × tipo de destino (24 metas; a origem nascia vazia, achado CAD-01, resolvido na origem conforme a decisão 2 da Seção 6) |

Comparativos "vs ano anterior / vs mês anterior" e faixas de exibição são **apresentação**, não dimensão.

## 5. A matriz de barramento

| fato \ dimensão | data | cliente | item | geografia | galpão | modalidade | transportador | motivo atraso | tipo oper. | veículo | faixa peso | fornecedor | meta frete |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| ft_estoque_foto | X | X | X | | X | | | | | | | | |
| ft_recebimento | X | X | X | | X | | | | | | | X | |
| ft_agendamento | X | X | | | X | | | | | X | | X | |
| ft_saida | X | X | X | | X | X | | | | | | | |
| ft_tracking | X | X | X | X | | X | X | X | | X | | | |
| ft_frete | X | X | | X | | X | X | | | X | X | | X |
| ft_validade | X | X | X | | X | | | | | | | | |
| ft_inventario | X | | | | X | | | | | | | | |
| ft_mc_operacao | X | X | | X | | X | | | X | X | | | |
| ft_armazenagem_cobranca | X | X | | | | | | | X | | | | |

Cada X é uma chave substituta (`sk_*`) apontando para a mesma dimensão, e é isso que garante, por construção, que **OTIF, receita e estoque signifiquem a mesma coisa em qualquer painel**: as dimensões são únicas, os painéis só escolhem quais fatos olhar.

## 6. Decisões pendentes de aprovação

1. **Grão do tracking:** manter o grão **item de pedido** (como o painel original opera, com contagens distintas de pedido para os indicadores de pedido) ou desdobrar em `ft_pedido` (grão pedido) + `ft_pedido_item`? Recomendação: **um só fato no grão item**, fiel ao uso do painel e mais simples de manter.
2. **Metas de frete (CAD-01):** a tabela `meta_frete` chegou vazia do staging. Metas são **parametrização de negócio**, não dado operacional; a recomendação é **populá-la no gerador como cadastro legítimo** (regiões × tipos de destino) na próxima regeneração, e não inventá-la na gold. **Aprovado e implementado em 2026-09-02:** o gerador passou a criar 24 metas (6 regiões × 4 tipos de destino), a `dim_meta_frete` existe e a `ft_frete` carrega `sk_meta_frete`.
3. **Ordem de construção:** as fatos do Painel 1 primeiro (o primeiro dashboard da vitrine), depois as do Painel 2. Produção e outros temas entram por demanda, pela mesma matriz.

---

[Início](#topo)
