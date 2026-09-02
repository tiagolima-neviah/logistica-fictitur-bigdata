<a id="topo"></a>

# Camada Bronze — o staging congelado em parquet

<!-- nav:start -->
[Home](../README.md) | [← Guia de Reprodução](05_guia_reproducao.md) | [Catálogo de Achados →](07_catalogo_achados_silver.md)
<!-- nav:end -->

> A primeira camada do lake: um espelho fiel das 50 tabelas do staging em arquivos parquet, com metadados de linhagem e verificação de contagens. A partir daqui o pipeline analítico não toca mais o banco: lê arquivos, baratos de guardar e rápidos de varrer, no storage que você escolher.

## 1. O que a camada é (e o que ela se proíbe de ser)

O bronze é **espelho, não interpretação**: nenhum filtro, nenhum rename, nenhuma correção. Se o staging tem uma data de 1899 ou um item sem valor unitário, o bronze carrega a sujeira adiante, porque tratar é trabalho da silver, e tratamento sem original preservado é adulteração sem prova. As duas únicas colunas que o bronze acrescenta são metadados de linhagem, não de negócio: `_extraido_em` (quando a extração rodou) e `_origem` (de que tabela do staging a linha veio).

## 2. Como rodar

Com o staging populado (ver o [Guia de Reprodução](05_guia_reproducao.md)):

```bash
uv run bronze-staging
```

A extração descobre as tabelas pelo catálogo do Postgres (tabela nova no staging entra sozinha), transfere cada uma em **streaming Arrow** (driver ADBC, os tipos do banco preservados com fidelidade) e grava parquet comprimido com zstd. Na base de referência: **~24,9 milhões de linhas em ~21 segundos**, ocupando **~360 MB** em parquet contra ~3,5 GB no Postgres, uma compressão de cerca de 10 vezes que ilustra por que formato colunar é o padrão de camada analítica.

Ao final, o extrator **confere as contagens** de cada parquet contra o staging e termina com erro em qualquer divergência; um `_manifesto.json` registra a execução (quando, quanto, onde, veredito).

## 3. Onde os arquivos vivem: storage como configuração

O destino é a variável `LAKE_URL` do `.env` (padrão: `data/lake`, dentro do projeto e fora do git). O acesso é abstraído por fsspec, então trocar de storage é trocar a URL, nunca o código: `data/lake` no notebook do analista, `s3://meu-bucket/lake` num MinIO on-premises ou na nuvem. É a portabilidade prometida na arquitetura: o mesmo pipeline no laptop, no CPD ou no cloud.

```
data/lake/
└── bronze/
    ├── _manifesto.json
    ├── cadastro/    (20 tabelas .parquet)
    ├── fwm/         (17)
    ├── expedicao/   (6)
    ├── faturamento/ (3)
    └── financeiro/  (4)
```

## 4. Verificações de saúde

```bash
uv run python -c "import pyarrow.parquet as pq; t = pq.read_table('data/lake/bronze/fwm/pedido.parquet'); print(t.num_rows, 'pedidos |', t.schema.names[-2:])"
```

Esperado: `1033263 pedidos | ['_extraido_em', '_origem']`. O `_manifesto.json` do diretório bronze traz o retrato completo da última execução.

---

[Início](#topo)
