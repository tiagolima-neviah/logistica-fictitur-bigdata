<a id="topo"></a>

# Warehouse Multidimensional — a gold servida em Postgres

<!-- nav:start -->
[Home](../README.md) | [← Camada Gold](10_camada_gold.md)
<!-- nav:end -->

> A última etapa do pipeline: o star schema da gold carregado num Postgres dimensional (o **warehouse**, `dw_fictitur`), pronto para Power BI, ferramentas de BI e qualquer cliente SQL. Nasce num segundo container do mesmo `docker compose`, é carregado **partição a partição** com prestação de contas, e o mesmo script serve um destino na nuvem trocando variáveis de ambiente.

## 1. Por que um banco relacional se a gold já existe em parquet

Parquet + DuckDB é a camada analítica ideal para pipeline e notebooks (OLAP colunar, sem servidor). Mas as ferramentas de apresentação do mercado (Power BI, Metabase, qualquer dashboard que fale SQL por conexão) esperam um **banco**: é o papel do warehouse, a encarnação **ROLAP** do star schema (as mesmas 13 dimensões e 10 fatos, em tabelas `dim.*` e `fato.*`). Três encarnações do OLAP convivem no projeto: colunar no lake, relacional no warehouse, e o motor em memória do Power BI que herda o cubo clássico.

## 2. Como rodar

O serviço `warehouse` sobe junto com o staging (`docker compose up -d`, porta `5434`, banco `dw_fictitur`, credenciais `DW_*` do `.env`). Com a gold construída:

```bash
uv run carga-dw
```

O carregador usa o DuckDB como ponte (lê o parquet, escreve no Postgres pela extensão `postgres`, sem código de conversão de tipos). Dimensões são recriadas inteiras; fatos são carregadas **por partição**: para cada ano, `DELETE WHERE ano = X` e `INSERT` das linhas daquele ano. Recarregar um ano não toca nos outros, e a carga é idempotente. Na base de referência: **~11,8 milhões de linhas em ~35 segundos** na primeira carga.

**Carga seletiva:** `DW_ANOS=2024,2025,2026` no `.env` sobe só essas partições. É o mesmo mecanismo para um destino menor (ver Seção 4).

## 3. Prestação de contas e tamanho

Cada partição confronta a contagem no parquet com a contagem no Postgres; qualquer divergência derruba a carga com erro. O `_manifesto_warehouse.json` (na pasta gold do lake) registra o quadro completo e o tamanho do banco. Medido na base de referência, **após `VACUUM FULL`** (recargas deixam espaço morto até o vacuum):

| objeto | tamanho |
|---|---|
| banco `dw_fictitur` inteiro | ~1,6 GB |
| `fato.ft_tracking` (grão item, 4,5 M linhas) | ~700 MB |
| `fato.ft_saida` | ~450 MB |
| `fato.ft_mc_operacao` | ~170 MB |
| `fato.ft_frete` | ~150 MB |
| demais fatos e todas as dimensões | < 100 MB somados |

Dica de operação: depois de recarregar partições, rode `VACUUM` no banco (`docker exec fictitur_warehouse_postgres psql -U fictitur -d dw_fictitur -c VACUUM`) para devolver o espaço das linhas apagadas.

## 4. Levando para a nuvem (ou para qualquer outro Postgres)

O carregador não sabe onde o Postgres mora: aponte `DW_HOST`, `DW_PORT`, `DW_DB`, `DW_USER` e `DW_PASSWORD` para o destino (um Neon, um RDS, o SQL gerenciado que for) e rode o mesmo `carga-dw`. Para caber num plano gratuito de nuvem, que costuma oferecer menos de 1 GB, a tabela da Seção 3 mostra onde cortar sem perder a história: **carregar só os anos recentes** (`DW_ANOS`) e/ou deixar de fora as fatos de grão fino (`ft_saida`, a maior parte da `ft_tracking`), servindo os painéis com as fatos agregadas. A medição local, antes de subir, é exatamente para essa decisão ser feita com número, não com palpite.

## 5. O pipeline completo, em um parágrafo

Um banco relacional de origem (simulado pelo staging sintético) → **bronze** (espelho fiel em parquet) → **silver** (conformado por regras aprovadas, com prestação de contas) → **gold** (star schema particionado, provado pela régua) → **warehouse** (o mesmo modelo, servido em Postgres, carregado por partição). Cada seta tem um comando, cada camada tem a sua prova, e tudo roda no laptop de quem clonar: `docker compose up` até o warehouse pronto para o Power BI.

---

[Início](#topo)
