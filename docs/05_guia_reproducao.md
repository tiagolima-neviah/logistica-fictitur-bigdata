<a id="topo"></a>

# Guia de Reprodução — do clone ao staging validado

<!-- nav:start -->
[Home](../README.md) | [← Régua de Validação](04_regua_validacao.md)
<!-- nav:end -->

> O manual completo para reproduzir este projeto na sua máquina: pré-requisitos, o passo a passo comentado do clone até o banco populado e aprovado pela régua, verificações de saúde e a solução dos tropeços mais comuns. O gerador é determinístico: seguindo estes passos, você chega **exatamente** à mesma base que a nossa, byte a byte.

## 1. Pré-requisitos

| requisito | observação |
|---|---|
| Linux (ou WSL2 no Windows) | desenvolvido em Ubuntu 24.04 LTS; no Windows, use WSL2 e trabalhe DENTRO do filesystem Linux (`~/projetos`), nunca em `/mnt/c` |
| Docker + Docker Compose | o Postgres do staging vive num container |
| [uv](https://docs.astral.sh/uv/) | gerencia o Python 3.12 e as dependências (ele baixa o Python sozinho se faltar) |
| git | para clonar |
| ~10 GB livres em disco | o banco populado ocupa ~3,5 GB, mais imagem do Postgres e ambiente Python |
| 8 GB de RAM e 4 núcleos | 16 GB recomendado; o gerador é single-thread e leva ~15 min |

## 2. Passo a passo

**1. Clone e entre no projeto:**

```bash
git clone https://github.com/tiagolima-neviah/logistica-fictitur-bigdata.git
cd logistica-fictitur-bigdata
```

**2. Configure o ambiente (12-factor):** copie o exemplo e defina uma senha local qualquer para o Postgres (ela nunca sai da sua máquina):

```bash
cp .env.example .env
# edite o .env e troque STAGING_PASSWORD
```

**3. Suba o staging:** o Postgres nasce com os 5 schemas e as 50 tabelas criados pelo DDL no primeiro boot:

```bash
cd staging
docker compose --env-file ../.env up -d
cd ..
```

**4. Instale o ambiente Python:**

```bash
uv sync
```

**5. Popule o banco (o gerador determinístico, ~15 min):** quatro etapas: mundo cadastral → catálogo comercial → arco operacional 2020-2026 → recebimento/estoque/armazenagem. Ao final, ~22 milhões de linhas.

```bash
uv run gerador-staging
```

**6. Valide com a régua (o contrato de aceite):** 28 verificações de volumes, indicadores, fases, sujeira e margens. O resultado esperado é `28 aprovados, 0 reprovados`.

```bash
uv run regua-staging
```

**7. Explore:** conecte seu cliente SQL (DBeaver, psql) em `localhost:5433`, banco `db_fictitur`, com o usuário e a senha do seu `.env`.

## 3. Verificações de saúde

```bash
docker compose --env-file ../.env ps          # container "healthy"? (rode dentro de staging/)
```

```bash
docker exec fictitur_staging_postgres pg_isready -U fictitur -d db_fictitur
```

Contagem rápida de tabelas por schema (esperado: cadastro 20 · fwm 17 · expedicao 6 · faturamento 3 · financeiro 4):

```bash
docker exec fictitur_staging_postgres psql -U fictitur -d db_fictitur -c "SELECT table_schema, count(*) FROM information_schema.tables WHERE table_schema IN ('cadastro','fwm','expedicao','faturamento','financeiro') GROUP BY 1 ORDER BY 1"
```

## 4. Regenerar do zero

O gerador é idempotente: rodá-lo de novo sobre um banco populado apenas avisa e sai. Para regenerar tudo (destrói e recria o banco):

```bash
cd staging
docker compose --env-file ../.env down -v
docker compose --env-file ../.env up -d
cd ..
uv run gerador-staging
```

## 5. Tropeços comuns

| sintoma | causa e solução |
|---|---|
| `STAGING_PASSWORD ausente` | você não criou o `.env` (passo 2) |
| porta 5433 ocupada | troque `STAGING_PORT` no `.env` e suba de novo |
| `permission denied` no Docker | seu usuário precisa estar no grupo `docker` (`sudo usermod -aG docker $USER` e reabra o terminal) |
| gerador diz "já populado" | comportamento correto; para recomeçar, use a seção 4 |
| régua reprova algum check | a base não está íntegra (geração interrompida no meio, por exemplo): regenere do zero; banda estourada não se contorna |
| gerador muito lento | confirme que o projeto está no filesystem Linux (`~/...`), não em `/mnt/c` |

---

[Início](#topo)
