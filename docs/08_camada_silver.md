<a id="topo"></a>

# Camada Silver — o bronze conformado, com prestação de contas

<!-- nav:start -->
[Home](../README.md) | [← Catálogo de Achados](07_catalogo_achados_silver.md) | [Matriz de Barramento →](09_matriz_barramento.md)
<!-- nav:end -->

> A segunda camada do lake: as mesmas tabelas do bronze, agora conformadas pelas regras aprovadas no [Catálogo de Achados](07_catalogo_achados_silver.md). A silver não interpreta por conta própria: ela executa um contrato, e prova que executou exatamente ele: cada regra tem a medida prometida no catálogo congelada no código, e a execução **reprova a si mesma** se marcar uma linha a mais ou a menos do que prometeu.

## 1. O que a silver fez (e provou)

Na ordem aprovada (valores impossíveis primeiro, pelo motivo demonstrado no notebook 02):

1. **Valores impossíveis anulados com auditoria** (PED-01, EST-01): datas de entrega sentinela e validades absurdas viram `NULL` nas colunas conformadas, com o valor original preservado (`dt_entrega_original`, `dt_validade_original`) e flag de marcação. Nada se adivinha, nada se perde.
2. **Flags de estrutura** (PED-02/03, EST-03, CAD-02, FIN-01): timeline inconsistente no pedido, razão não-conciliado no movimento, item sem valor unitário, frete simbólico. Marcação pura: nenhum valor alterado.
3. **Seleção de colunas** (CAD-03): as colunas 100% nulas do catálogo de itens ficam fora da silver, detectadas em tempo de execução (se uma coluna morta ressuscitar num bronze futuro, a contagem diverge do catálogo e a auditoria acusa).

Todas as demais tabelas passam 1:1, preservando a linhagem do bronze.

## 2. Como rodar

```bash
uv run silver-staging
```

Na base de referência: **~24,9 milhões de linhas gravadas em ~3 segundos** (SQL DuckDB sobre parquet, gravando parquet zstd em `silver/`). A saída termina com a **prestação de contas**: cada regra com o executado ao lado do prometido, e o processo sai com erro em qualquer divergência: auditoria reprovada não é aviso, é bloqueio. O retrato fica em `silver/_auditoria.json`.

## 3. O contrato de quem consome

Quem lê a silver (gold, notebooks, dashboards) pode confiar em três garantias: **colunas conformadas são seguras** para cálculo de prazo e valor (o lixo está anulado e marcado, não misturado); **as flags são o mapa do risco** (quer excluir timelines inconsistentes de uma análise de duração? filtre `fl_timeline_inconsistente`); e **nada sumiu**: toda linha do bronze está na silver, e todo valor anulado tem seu original ao lado. A regra de ouro herdada do padrão da casa: quem transforma presta contas; quem consome, escolhe com as flags.

## 4. Limites desta camada

A silver não resolve os achados de negócio (vencidos com presença seguem lá, para a gold reportar), não concilia o razão de movimentos (a foto oficial é a autoridade de saldo, decisão registrada no catálogo) e não cria dados para os vazios estruturais (`meta_frete`, universo de serviços). O que ela entrega é um terreno onde esses problemas estão **visíveis e demarcados**, que é o máximo que uma camada de dados pode prometer com honestidade.

---

[Início](#topo)
