"""Construtor da gold: materializa o star schema em parquet a partir da silver.

Etapas: dimensões conformadas (G1) e, nas próximas entregas, as fatos por mart
(G2 pedidos, G3 margens, G4 materiais). Layout do lake:
`gold/dimensoes/dim_*.parquet` e `gold/fatos/<fato>/ano=YYYY/*.parquet`.

Uso: `uv run gold-staging` (com a silver construída).
"""

from __future__ import annotations

import time

import fsspec

from logistica_fictitur.config import url_lake
from logistica_fictitur.gold.dimensoes import DIMENSOES
from logistica_fictitur.lake import conectar


def main() -> None:
    inicio = time.monotonic()
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    conn = conectar()

    fs.makedirs(f"{raiz}/gold/dimensoes", exist_ok=True)
    print(f"Gold G1 — dimensões conformadas → {url_lake()}/gold/dimensoes\n")
    for nome, consulta in DIMENSOES.items():
        destino = f"{raiz}/gold/dimensoes/{nome}.parquet"
        conn.execute(
            f"COPY ({consulta}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        linha = conn.execute(f"SELECT count(*) FROM read_parquet('{destino}')").fetchone()
        print(f"  {nome.ljust(22)} {int(linha[0]) if linha else 0:>8} linhas")

    print(f"\nG1 concluída em {time.monotonic() - inicio:.1f}s."
          " Próximas etapas (fatos) em desenvolvimento.")


if __name__ == "__main__":
    main()
