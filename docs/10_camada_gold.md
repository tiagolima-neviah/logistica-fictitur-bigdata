<a id="topo"></a>

# Camada Gold — o star schema, construído e provado

<!-- nav:start -->
[Home](../README.md) | [← Matriz de Barramento](09_matriz_barramento.md) | [Warehouse →](11_warehouse_multidimensional.md)
<!-- nav:end -->

> A terceira camada do lake materializa o projeto dimensional da [Matriz de Barramento](09_matriz_barramento.md): 13 dimensões conformadas e 10 fatos, todas construídas da silver, em parquet particionado por ano. E, como toda camada deste projeto, ela prova o que fez: a **régua da gold** confere conservação, integridade e coerência antes de qualquer dashboard encostar nela.

## 1. O que existe na gold

**Dimensões** (`gold/dimensoes/dim_*.parquet`, únicas para todos os fatos): data (calendário 2019-2027 mais o membro especial "data inválida"), cliente (com o OTIF contratual), item (com m³ unitário e a flag do furo fiscal), geografia, galpão (com a dona), modalidade, fase, transportador, motivo de atraso, tipo de operação, veículo, faixa de peso e fornecedor.

**Fatos** (`gold/fatos/<fato>/ano=YYYY/*.parquet`), no grão da matriz:

| painel | fato | grão | linhas |
|---|---|---|---|
| Materiais | `ft_tracking` | item de pedido, com a data em três papéis (solicitação, **prazo prometido**, entrega) | ~4,5 M |
| Materiais | `ft_saida` | item de pedido expedido | ~4,4 M |
| Materiais | `ft_frete` | fatura de frete (SS), com faixa de peso | ~1,0 M |
| Materiais | `ft_recebimento` | item recebido por ordem de recebimento | ~579 mil |
| Materiais | `ft_estoque_foto` | foto mensal × item × galpão | ~159 mil |
| Materiais | `ft_agendamento` | agendamento de chegada | ~119 mil |
| Materiais | `ft_validade` | lote × item | ~10,5 mil |
| Materiais | `ft_inventario` | inventário | 209 |
| Margens | `ft_mc_operacao` | operação faturada (transporte por SS, armazenagem por cliente × mês, devoluções na competência do custo) | ~1,06 M |
| Margens | `ft_armazenagem_cobranca` | cliente × competência | ~9,2 mil |

Três decisões de desenho que valem entender: **medidas-base, não apresentação** (a gold não carrega "% de evolução" nem rankings: isso é trabalho do DAX e do dashboard); **a data com papéis** (a mesma `dim_data` entra na `ft_tracking` como solicitação, prazo ao cliente, prazo interno e entrega, porque o OTIF se apura pelo eixo da promessa); e **o membro "data inválida"** (`sk_data = -1`, partição `ano=-1`), o jeito Kimball de dar endereço a datas anuladas pela silver sem apagar linhas nem contaminar anos reais.

## 2. Como rodar e como provar

```bash
uv run gold-staging      # reconstrói dimensões e fatos (~2 s)
uv run regua-gold        # 25 checks de consistência interna
```

A régua da gold não compara com nenhuma referência externa: a gold precisa ser coerente **consigo mesma e com as camadas abaixo**. Três famílias de verificação: **conservação** (linhas e somas das fatos batem com a silver, ao centavo na receita), **integridade dimensional** (toda chave obrigatória resolve na sua dimensão) e **coerência de indicadores** (o OTIF por ano apurado na gold cai nas mesmas bandas da régua do staging, e as margens também: a história sobrevive às três camadas). Uma reprovação significa reconstruir depois de achar a causa, nunca ajustar o número.

## 3. Particionamento: por que pastas por ano

Cada fato é gravada em subpastas `ano=YYYY` (layout hive). Consulta que filtra período lê só as pastas daquele período (*partition pruning*); a partição vira também **unidade de carga** (o warehouse relacional pode receber só 2024-2026) e **unidade de auditoria** (contagem por ano no parquet contra contagem por ano no banco). É o mesmo conceito da tabela particionada por intervalo do SQL Server/Postgres, em arquivos, e o layout que Spark e Athena usam.

## 4. Como consumir

Pelo motor do projeto, cada fato e dimensão é uma view: `gold_fatos_ft_tracking`, `gold_dimensoes_dim_cliente`... O [notebook 04](../notebooks/04_demonstracao_gold.ipynb) mostra seis perguntas respondidas com SQL sobre elas. Regra de leitura da `ft_tracking`: medidas de item somam (`SUM`); indicadores de pedido contam pedidos distintos (`COUNT(DISTINCT ss)`), porque o grão é o item.

---

[Início](#topo)
