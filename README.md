<a id="topo"></a>

# Fictitur Logística · Pipeline de BI ponta a ponta

<!-- nav:start -->
[Entendimento do Negócio](docs/01_entendimento_negocio.md) | [Entendimento dos Dados](docs/02_entendimento_dados.md) | [Modelo de Dados](docs/03_modelo_dados_staging.md) | [Régua de Validação](docs/04_regua_validacao.md) | [Guia de Reprodução](docs/05_guia_reproducao.md)
<!-- nav:end -->

> Pipeline completo e moderno de Business Intelligence construído sobre a **Fictitur Logística**, uma operadora logística **fictícia** com dados **100% sintéticos**: do banco relacional de origem ao staging, do staging às camadas bronze, silver e gold em parquet, da gold ao modelo multidimensional (star schema) carregado em banco relacional, pronto para dashboards web e Power BI. O repositório existe para ajudar analistas em início de carreira a percorrer um projeto de engenharia de dados e BI do jeito que ele acontece no mundo real, com custo baixo e total portabilidade.

> **Aviso:** a Fictitur Logística não existe. Empresa, clientes, pessoas, códigos, documentos e valores são fictícios e gerados sinteticamente. Este projeto não possui afiliação com nenhuma empresa real; qualquer semelhança é coincidência.

## ⚠️ Disclaimer: projeto de estudo, não use em produção

Este repositório é um **CASE fictício com dados sintéticos, criado exclusivamente para fins de estudo**. Ele **não deve, em hipótese alguma, ser usado em ambiente de produção real**: por ser material didático, conceitos essenciais de segurança da informação foram deliberadamente deixados de fora do escopo, e códigos, containers e configurações aqui presentes são frágeis por concepção (senhas em `.env` local, serviços sem hardening, ausência de criptografia, controle de acesso e trilha de auditoria).

O software é fornecido **"no estado em que se encontra" (AS IS), sem garantias de qualquer natureza**, nos termos da [licença MIT](LICENSE) deste repositório. Os autores e a Neviah **não se responsabilizam por quaisquer danos** decorrentes do uso deste material; qualquer utilização fora do contexto de estudo, incluindo ambientes produtivos, é feita **por conta e risco exclusivos de quem a fizer**.

Tem interesse em implementar este projeto de verdade na sua empresa? Entre em contato pela **[www.neviah.com.br](https://www.neviah.com.br)**: a implementação real é feita de forma completa e correta, considerando todas as políticas de segurança da informação e de proteção de dados (LGPD).

## Por que este projeto existe

A maioria dos tutoriais de BI começa num CSV limpo e termina num gráfico. A realidade de uma PME é outra: um banco transacional sobrecarregado, relatórios que não batem entre si, planilhas paralelas por todo lado e nenhum orçamento para Databricks ou nuvem cara. Este projeto simula exatamente esse cenário e o resolve com uma arquitetura portável e de baixo custo: Postgres, Python, parquet e Docker, com storage abstraído para rodar tanto no notebook do analista quanto num CPD ou na nuvem, sem reescrever o pipeline. A empresa cresceu? O mesmo pipeline vai junto.

## O caso

A Fictitur Logística (matriz em São Paulo, 4 galpões, 36 bases parceiras pelo Brasil, mais de 200 clientes) opera armazenagem e entregas. Ela relata duas dores: relatórios que divergem entre si e lentidão no banco de produção, porque as cargas do BI concorrem com o sistema transacional no mesmo servidor. A solução contratada: um ambiente de **staging** que espelha o banco relacional com carga incremental diária, tirando o peso da produção, e um pipeline analítico que reconstrói os indicadores de forma consistente, de uma única fonte da verdade. A história completa está no [Entendimento do Negócio](docs/01_entendimento_negocio.md).

## Arquitetura

```
Banco relacional de origem (simulado)
        │  carga incremental diária
        ▼
Staging (Postgres em Docker, 5 schemas, 50 tabelas)
        ▼
Bronze ──► Silver ──► Gold (parquet; storage via fsspec: file:// ↔ s3://)
                        ▼
              Star schema multidimensional
                        ▼
     Destino configurável por .env (Postgres, Neon, SQL Server...)
                        ▼
            Dashboards web e Power BI
```

## Status do projeto

| etapa | situação |
|---|---|
| Modelo relacional + DDL (staging) | concluído |
| Staging Postgres no Docker | concluído |
| Régua de validação dos dados sintéticos | concluído (28 checks) |
| Gerador de dados sintéticos (2020-2026, ~22M linhas) | concluído e aprovado 28/28 |
| Bronze (staging → parquet via fsspec, ~25M linhas em ~21s) | concluído |
| Auditoria de qualidade (3 notebooks, 11 achados) + catálogo de regras | concluído |
| Silver (regras aprovadas + prestação de contas, ~25M linhas em ~3s) | concluído |
| Gold (datamarts) | a iniciar |
| Star schema + carga no destino | a iniciar |
| Dashboards | a iniciar |

## Requisitos

**Máquina (estimativa, a consolidar):** 8 GB de RAM (16 recomendado), 4 núcleos, ~30 GB livres em disco.

**Sistema:** o projeto foi desenvolvido em **Ubuntu 24.04 LTS** (via WSL2 no Windows 11). Usuários de Windows devem usar o **WSL2**; usuários de Linux/macOS rodam nativo. Ferramentas: **Docker + Docker Compose**, **Python 3.12**, **git**. Recomendado: [uv](https://docs.astral.sh/uv/) para o ambiente Python e um cliente SQL (DBeaver, psql).

**Conhecimentos que ajudam:** SQL, Python básico, noções de Docker e terminal Linux. Cada etapa da documentação explica o que faz e por quê; o objetivo é que um analista em formação consiga acompanhar.

## Como rodar (estado atual)

```bash
cd ~                        # SEMPRE no filesystem do Linux; /mnt/c degrada muito a performance
git clone https://github.com/tiagolima-neviah/logistica-fictitur-bigdata.git
cd logistica-fictitur-bigdata
cp .env.example .env        # edite STAGING_PASSWORD
cd staging && docker compose --env-file ../.env up -d && cd ..
uv sync
uv run gerador-staging      # popula 2020-2026 (~15 min, determinístico)
uv run regua-staging        # valida: esperado 28 aprovados, 0 reprovados
```

O Postgres sobe na porta `5433` (configurável no `.env`) com o banco `db_fictitur`; o gerador popula ~22 milhões de linhas cobrindo 2020 a 2026 e a régua dá o veredito. O manual completo, com verificações de saúde e solução de problemas, está no [Guia de Reprodução](docs/05_guia_reproducao.md).

## Estrutura de diretórios

```
logistica-fictitur-bigdata/
├── README.md            # este hub
├── LICENSE              # MIT (software fornecido AS IS, sem garantias)
├── .env.example         # configuração 12-factor (copie para .env; o .env não é versionado)
├── pyproject.toml       # pacote Python + esteira de qualidade (ruff, mypy, pytest)
├── docs/                # documentação do projeto (negócio, dados, manuais)
├── src/logistica_fictitur/
│   └── validacao/       # régua de validação: bandas versionadas + verificador
├── tests/               # testes da esteira de qualidade
└── staging/
    ├── docker-compose.yml
    └── ddl/             # DDL dos 5 schemas do banco de staging (00..05)
```

## Documentação

<details open>
<summary><strong>Regras de negócio e documentação técnica</strong> (leia na ordem)</summary>

**Fundação**

- [01 · Entendimento do Negócio](docs/01_entendimento_negocio.md): quem é a Fictitur, como opera, as dores e o objetivo do projeto.
- [02 · Entendimento dos Dados](docs/02_entendimento_dados.md): os 5 schemas e o papel de cada grupo de tabelas, em linguagem de negócio.
- [03 · Modelo de Dados do Staging](docs/03_modelo_dados_staging.md): a referência técnica, com o diagrama e o objetivo de cada uma das 50 tabelas.
- [04 · Régua de Validação](docs/04_regua_validacao.md): o contrato de aceite dos dados sintéticos e como rodá-lo.
- [05 · Guia de Reprodução](docs/05_guia_reproducao.md): o manual completo do clone ao staging validado, com healthchecks e troubleshooting.

**Camadas do lake**

- [06 · Camada Bronze](docs/06_camada_bronze.md): o staging congelado em parquet, com linhagem, verificação de contagens e storage plugável.
- [07 · Catálogo de Achados da Silver](docs/07_catalogo_achados_silver.md): os achados da auditoria de qualidade e as regras de tratamento, o contrato da camada.
- [08 · Camada Silver](docs/08_camada_silver.md): o bronze conformado pelas regras aprovadas, com a prestação de contas que reprova a si mesma em divergência.
- [09 · Matriz de Barramento](docs/09_matriz_barramento.md): dos indicadores dos painéis ao star schema: grãos, fatos, dimensões conformadas e a matriz Kimball, o contrato da gold.

</details>

<details>
<summary><strong>Notebooks</strong> (executados, com as evidências e os gráficos)</summary>

**Auditoria de qualidade do bronze**

- [01 · Cadastro](notebooks/01_qualidade_cadastro.ipynb)
- [02 · Pedidos e entregas](notebooks/02_qualidade_pedidos_entregas.ipynb)
- [03 · Estoque e financeiro](notebooks/03_qualidade_estoque_financeiro.ipynb)

**Demonstração**

- [04 · Demonstração da gold](notebooks/04_demonstracao_gold.ipynb): seis perguntas de negócio respondidas pelo star schema, com gráficos (OTIF pelo eixo da promessa, sazonalidade, porte, receita por região, estoque, no-show).

</details>

Rotinas de manutenção adicionais serão publicadas junto com o pipeline.

---

[Início](#topo)
