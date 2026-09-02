"""Construtor da gold: materializa o star schema em parquet a partir da silver.

G1: dimensões conformadas em `gold/dimensoes/dim_*.parquet`.
G3: fatos do Painel 1 em `gold/fatos/<fato>/ano=YYYY/*.parquet` (partição hive,
padrão aprovado: partição = unidade de carga e de auditoria).

Uso: `uv run gold-staging` (com a silver construída). Idempotente: dimensões e
partições são sobrescritas a cada execução.
"""

from __future__ import annotations

import time

import fsspec

from logistica_fictitur.config import url_lake
from logistica_fictitur.gold.dimensoes import DIMENSOES
from logistica_fictitur.gold.fatos import FATOS
from logistica_fictitur.lake import conectar


def main() -> None:
    inicio = time.monotonic()
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    conn = conectar()

    fs.makedirs(f"{raiz}/gold/dimensoes", exist_ok=True)
    print(f"Gold G1 — dimensões conformadas → {url_lake()}/gold/dimensoes")
    for nome, consulta in DIMENSOES.items():
        destino = f"{raiz}/gold/dimensoes/{nome}.parquet"
        conn.execute(
            f"COPY ({consulta}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        # a dimensão recém-gravada fica visível para as fatos desta mesma execução
        conn.execute(
            f"CREATE OR REPLACE VIEW gold_dimensoes_{nome} AS"
            f" SELECT * FROM read_parquet('{destino}')"
        )
        linha = conn.execute(f"SELECT count(*) FROM read_parquet('{destino}')").fetchone()
        print(f"  {nome.ljust(22)} {int(linha[0]) if linha else 0:>9} linhas")

    fs.makedirs(f"{raiz}/gold/fatos", exist_ok=True)
    print(f"\nGold G3 — fatos do Painel 1 (particionadas por ano) → {url_lake()}/gold/fatos")
    total = 0
    for nome, consulta in FATOS.items():
        pasta = f"{raiz}/gold/fatos/{nome}"
        if fs.exists(pasta):
            fs.rm(pasta, recursive=True)  # partições antigas não sobrevivem (idempotência)
        conn.execute(
            f"COPY ({consulta}) TO '{pasta}'"
            " (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (ano))"
        )
        linha = conn.execute(
            f"SELECT count(*), count(DISTINCT ano)"
            f" FROM read_parquet('{pasta}/*/*.parquet', hive_partitioning = true)"
        ).fetchone()
        n, particoes = (int(linha[0]), int(linha[1])) if linha else (0, 0)
        total += n
        print(f"  {nome.ljust(22)} {n:>9} linhas em {particoes:>2} partições")

    print(f"\nGold concluída: {total} linhas de fato em {time.monotonic() - inicio:.1f}s.")


if __name__ == "__main__":
    main()
