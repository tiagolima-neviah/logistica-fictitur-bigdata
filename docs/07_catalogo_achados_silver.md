<a id="topo"></a>

# Catálogo de Achados e Regras da Silver

<!-- nav:start -->
[Home](../README.md) | [← Camada Bronze](06_camada_bronze.md) | [Camada Silver →](08_camada_silver.md)
<!-- nav:end -->

> O contrato da camada silver: os 11 achados da auditoria de qualidade do bronze (notebooks 01 a 03), cada um com sua medida, a regra de tratamento proposta e o princípio que a ampara. **Nenhuma transformação roda antes deste catálogo ser aprovado pelo dono do projeto**; depois de aprovado, a silver presta contas contra ele: cada alteração feita precisa corresponder a uma regra daqui, e nenhuma regra pode alterar mais (nem menos) do que prometeu.

## 1. Os princípios que amarram as regras

Cinco regras invioláveis governam qualquer tratamento neste projeto: o **bronze é intocável** (a silver escreve camada nova, jamais reescreve a origem); **ausência não se preenche** (dado faltante se marca, não se inventa); **duplicidade se marca, não se funde**; **toda limpeza presta contas** (auditoria de o quê, quanto e por qual regra); e **tratamento é idempotente** (rodar duas vezes dá o mesmo resultado). Um sexto princípio nasceu nesta auditoria: **valor impossível se anula e se preserva**, ou seja, a coluna conformada fica nula com flag, e o valor original sobrevive em coluna de auditoria.

## 2. O catálogo (medidas dos notebooks 01–03, base de 2026-09-02)

| código | achado | medida | regra proposta na silver |
|---|---|---|---|
| CAD-01 | `meta_frete` sem nenhuma linha | 0 linhas | Documentar como vazio estrutural; a silver não a cria (ausência não se preenche) |
| CAD-02 | Itens sem valor unitário (furo de cobertura fiscal) | 112 itens (1,65%) | `fl_sem_valor_unitario = true`; preço não se inventa; indicadores de valor excluem ou destacam esses itens |
| CAD-03 | Colunas 100% nulas no catálogo de itens (`url_foto`, `material`, `classe_anvisa`, `cod_item_cliente` parcial¹) | 4 colunas | Colunas 100% nulas ficam FORA da silver de itens; documentadas aqui como cadastro incompleto de origem |
| PED-01 | Entregas com data impossível (sentinelas 1899-12-30, 2055-08-11, 2098-08-22) | 5.126 entregas (0,50%) | `dt_entrega_conformada = NULL` + `fl_data_entrega_invalida = true` + valor original preservado em `dt_entrega_original`; a data verdadeira não se adivinha |
| PED-02 | Linha do tempo de fases fora de ordem cronológica | 26.262 pedidos (2,54%) | `fl_timeline_inconsistente = true` no pedido; **fases não se reordenam** (timeline não se conserta por palpite); pedidos marcados saem das apurações de duração por fase |
| PED-03 | Recorte do PED-02 com data de entrega plausível (apontamento retroativo) | 24.520 pedidos | Mesma flag do PED-02; registrado à parte porque sobrevive ao tratamento do PED-01 e é o caso a discutir com a operação |
| EST-01 | Lotes com validade absurda (além de 2040) | 47 lotes | `dt_validade_conformada = NULL` + `fl_validade_invalida = true` + original preservado |
| EST-02 | Itens com lote vencido e presença na última foto | 209 itens | **Nenhum tratamento**: é achado de NEGÓCIO, não defeito de dado; permanece intacto e vira indicador na gold (aging/vencidos) |
| EST-03 | Razão de movimentos não concilia com a foto oficial (100% dos itens comparáveis divergem; 49 com saldo teórico negativo) | 1.983 itens divergentes | Decisão de fonte da verdade: **a foto oficial (`estoque_snapshot`) é a autoridade de saldo e cobrança**; o movimento recebe `fl_razao_nao_concilia` no nível do item e serve apenas a análises de fluxo relativo. **Premissa a validar com o dono do processo** |
| FIN-01 | Faturas de frete com valor simbólico (retiradas a R$ 0,01) | 124.108 faturas (12,0%) | `fl_frete_simbolico = true`; linhas preservadas; indicadores de receita média e ticket excluem as marcadas (o ticket médio muda de ~3.720 para ~4.230 sem elas) |
| FIN-02 | Universo de serviços sem nenhuma linha (`os`, `coleta`, `positivacao`, `servico_complementar`, `fatura_servico`) | 5 tabelas | Documentar como limite de escopo da base v1 (o BI de margens cobre transporte e armazenagem); nada se inventa |

¹ `cod_item_cliente` tem nulos parciais estruturais e permanece; as excluídas são apenas as 100% nulas.

### 2.1 Adendo aprovado em 2026-09-02 (achado da régua da gold)

| código | achado | medida | regra aprovada na silver |
|---|---|---|---|
| FIN-03 | Lançamentos de custo de devolução/reentrega com competência impossível (herdada de entregas com data-sentinela: 1900, 2055, 2098) | 73 lançamentos (0,008% das linhas, 0,004% do valor) | `competencia` e `dt_lancamento` anulados + originais preservados + `fl_competencia_invalida = true`, o mesmo padrão do PED-01; na gold, o membro especial "data inválida" da `dim_data` (`sk_data = -1`) recebe essas linhas na partição `ano=-1`, para que nada suma e nada contamine os anos reais. Impacto financeiro desprezível, impacto estrutural real (partições fantasmas e chaves sem calendário) |

## 3. Ordem de aplicação (e por quê)

1. **Sentinelas e impossíveis primeiro** (PED-01, EST-01): o notebook 02 demonstrou que datas impossíveis se disfarçam de "atraso sem justificativa"; qualquer regra que leia datas antes desta produz falso achado.
2. **Flags de estrutura** (PED-02/03, EST-03, CAD-02, FIN-01): marcações que não alteram valor.
3. **Seleção de colunas** (CAD-03): a silver nasce sem as colunas mortas.
4. Vazios estruturais (CAD-01, FIN-02) não geram passo de execução: geram documentação.

## 4. Prestação de contas (o que a silver vai reportar)

Ao final da execução, a silver publica um **relatório de auditoria** com, por regra: linhas lidas, linhas marcadas, células anuladas (com contagem por coluna) e o confronto com as medidas deste catálogo. Divergência entre o prometido aqui e o executado lá **é defeito da silver**, não licença para ajustar o catálogo em silêncio: catálogo só muda com nova aprovação.

## 5. O que a silver NÃO fará

Não preenche datas nem preços; não reordena timelines; não funde registros; não apaga linhas (nem as de data impossível: elas ficam, marcadas); não corrige o razão de movimentos; não cria dados para os vazios estruturais. Tudo que estiver fora da tabela da Seção 2 está fora do escopo aprovado.

---

[Início](#topo)
