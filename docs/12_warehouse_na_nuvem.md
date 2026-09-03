<a id="topo"></a>

# Warehouse na Nuvem: o mesmo carregador, um Postgres gratuito on-line

<!-- nav:start -->
[Home](../README.md) | [← Warehouse Multidimensional](11_warehouse_multidimensional.md)
<!-- nav:end -->

> O último passo do pipeline: levar o star schema para um Postgres na nuvem, gratuito, acessível de qualquer lugar. Serve para quem quer treinar SQL num modelo dimensional de verdade, montar um relatório de portfólio no Power BI ou no Tableau, ou apontar um dashboard web para um banco que não depende do laptop ligado. Este documento foi escrito **depois** de a carga ter sido feita e conferida numa conta real; cada número aqui foi medido.

## 1. O que muda em relação ao container local

Nada no código. O carregador (`carga-dw`) não sabe onde o Postgres mora: ele lê a conexão do ambiente e faz o mesmo rito, dimensões inteiras e fatos partição a partição, conferindo contagens no fim. A única decisão nova é **quanto cabe**: um plano gratuito costuma oferecer cerca de 0,5 GB, e o warehouse completo tem ~1,6 GB. A medição da [Seção 3 do docs/11](11_warehouse_multidimensional.md#3-prestação-de-contas-e-tamanho) mostra onde cortar sem quebrar o modelo: por **ano**, que é a unidade de carga.

| recorte (`DW_ANOS`) | tamanho após VACUUM | cabe em 0,5 GB? |
|---|---|---|
| `2026` | 232 MB | sim, com folga para índices |
| `2025,2026` | 548 MB | não |
| `2024,2025,2026` | 832 MB | não |

O recorte de um ano preserva **todas as 14 dimensões inteiras** (o calendário de 2020 a 2028, os 203 clientes, os 6.804 itens, as 24 metas de frete) e as **10 fatos com as linhas de 2026**. Para a história completa de 2020 a 2026, o parquet da gold (161 MB) continua sendo a fonte, e é ele que o dashboard web consome.

## 2. Passo a passo (Neon, plano gratuito)

Usamos o [Neon](https://neon.com) porque tem plano gratuito com Postgres 16 e string de conexão padrão, sem cartão de crédito. Não há qualquer vínculo entre este projeto e a empresa; qualquer Postgres serve (RDS, Supabase, Railway, um servidor seu), e os passos são os mesmos: obter a string de conexão e apontar o carregador para ela.

**1. Crie o projeto no console do Neon.** Região mais próxima (para o Brasil, `sa-east-1`), banco e usuário padrão servem. O console entrega uma string de conexão no formato:

```
postgresql://USUARIO:SENHA@ep-xxxx-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

**2. Guarde a conexão num arquivo separado**, para o `.env` continuar apontando para o container local. O padrão `.env.*` já está no `.gitignore`; esse arquivo **nunca** é versionado.

```bash
cat > .env.neon <<'EOF'
DW_URL=postgresql://USUARIO:SENHA@ep-xxxx-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
DW_ANOS=2026
EOF
```

Use o host **sem** o sufixo `-pooler` para a carga: o endpoint com pooler passa por um PgBouncer, feito para muitas conexões curtas (as ferramentas de consulta), não para uma sessão longa que cria schemas e insere centenas de milhares de linhas.

**3. Rode o carregador apontando para o arquivo:**

```bash
uv run carga-dw --env .env.neon
```

Saída esperada (medida em 2026-09-03, de São Paulo para `sa-east-1`):

```
Warehouse: dimensões (recriadas inteiras)
  dim.dim_data                  3288
  ...
  dim.dim_meta_frete              24
Warehouse: fatos, partição a partição (DELETE ano + INSERT)
  fato.ft_tracking                 635435 linhas em  1 partições
  fato.ft_saida                    583352 linhas em  1 partições
  ...
Tamanho do warehouse: 232 MB · 159.2s.
Carga APROVADA: toda partição confere parquet × warehouse. Manifesto gravado.
```

Os ~2,5 minutos são a rede (o container local faz o mesmo recorte em 3 segundos). A conferência parquet × warehouse é a mesma do container: se uma partição divergir, a carga reprova.

**4. Repetir é seguro.** Rodar de novo apaga e reinsere só as partições pedidas; trocar `DW_ANOS` troca o recorte. Depois de recargas, um `VACUUM` no banco devolve o espaço das linhas apagadas.

## 3. Conectando de qualquer lugar

Para consultas, use o host **com** `-pooler` (é o que o console do Neon mostra por padrão). Os dados de conexão são os da string: host, porta `5432`, banco `neondb`, usuário e senha, **SSL obrigatório**.

| ferramenta | como |
|---|---|
| **DBeaver** (Community, gratuito) | Nova conexão → PostgreSQL → host, banco, usuário, senha; na aba SSL, marque "Use SSL" (modo `require`). Os schemas `dim` e `fato` aparecem na árvore. |
| **Power BI Desktop** | Obter dados → Banco de dados PostgreSQL → servidor `host:5432`, banco `neondb`; modo **Importação** (o relatório publicado carrega os dados consigo e não depende do banco ficar acordado). |
| **Tableau** | Conectar → PostgreSQL → mesmos dados, com "Require SSL". |
| **Python / DuckDB** | `ATTACH '<DW_URL>' AS dw (TYPE postgres, READ_ONLY)` e consulte `dw.fato.*` e `dw.dim.*`. |
| **psql** | `psql "<DW_URL>"` |

Medido pelos dois endpoints, de fora: conexão em menos de 1 segundo; a consulta abaixo (OTIF por região sobre os 635 mil itens de pedido de 2026) responde em ~1 segundo.

```sql
SELECT g.regiao_comercial,
       count(DISTINCT t.ss) AS pedidos,
       round(100.0 * count(DISTINCT t.ss) FILTER (WHERE t.fl_no_prazo)
             / nullif(count(DISTINCT t.ss) FILTER (WHERE t.fl_entregue
                                                    AND NOT t.fl_data_entrega_invalida), 0), 1) AS otif
FROM fato.ft_tracking t
JOIN dim.dim_geografia g ON g.sk_geografia = t.sk_geografia
GROUP BY 1 ORDER BY 2 DESC;
```

## 4. O que esperar de um plano gratuito

- **Armazenamento** em torno de 0,5 GB: por isso o recorte de um ano. Índices contam no total; crie-os com parcimônia (chaves `sk_*` das fatos maiores são os candidatos).
- **Compute que dorme**: sem consultas por alguns minutos, o servidor suspende; a primeira consulta seguinte acorda em poucos segundos. Para demo e estudo é irrelevante; para um dashboard público com tráfego, é um dos motivos de o [projeto de visualização](../README.md#arquitetura) ler o parquet da gold com DuckDB embutido em vez de depender do banco.
- **Sem cartão, sem custo**: nada neste projeto exige plano pago. Se o plano gratuito mudar de limites, a tabela da Seção 1 é a referência para escolher outro recorte.

## 5. Fechamento do pipeline

Com este passo, o ciclo está completo: banco relacional de origem → bronze → silver → gold → warehouse local → **warehouse na nuvem**, tudo com o mesmo código, o mesmo `.env.example` e a mesma prestação de contas. O que vem depois não é mais pipeline: é a camada de visualização, no repositório do dashboard.

---

[Início](#topo)
