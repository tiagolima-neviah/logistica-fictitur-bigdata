"""Acesso analítico ao lake: uma conexão DuckDB que enxerga as camadas em parquet.

O DuckDB é o motor de transformação e varredura do pipeline: SQL direto sobre
os arquivos parquet, sem servidor. Esta fábrica registra atalhos (views) para
cada tabela do lake, então consultas e notebooks escrevem
`SELECT ... FROM bronze_fwm_pedido` em vez de repetir caminhos de arquivo.
"""

from __future__ import annotations

import duckdb
import fsspec

from logistica_fictitur.config import url_lake

CAMADAS = ("bronze", "silver", "gold")


def conectar() -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB em memória com uma view por parquet existente no lake.

    A view chama `<camada>_<schema>_<tabela>` (ex.: `bronze_fwm_pedido`).
    Arquivos novos entram sozinhos na próxima conexão.
    """
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    conn = duckdb.connect()
    for camada in CAMADAS:
        if not fs.exists(f"{raiz}/{camada}"):
            continue
        for caminho in fs.glob(f"{raiz}/{camada}/*/*.parquet"):
            partes = str(caminho).replace("\\", "/").split("/")
            schema, arquivo = partes[-2], partes[-1].removesuffix(".parquet")
            view = f"{camada}_{schema}_{arquivo}"
            caminho_sql = str(caminho).replace("'", "''")
            conn.execute(
                f"CREATE VIEW \"{view}\" AS SELECT * FROM read_parquet('{caminho_sql}')"
            )
        # fatos particionadas (hive): gold/fatos/<fato>/ano=YYYY/*.parquet → uma view por fato
        for pasta in fs.glob(f"{raiz}/{camada}/*/*/ano=*"):
            partes = str(pasta).replace("\\", "/").split("/")
            schema, fato = partes[-3], partes[-2]
            view = f"{camada}_{schema}_{fato}"
            base = "/".join(partes[:-1]).replace("'", "''")
            conn.execute(
                f"CREATE OR REPLACE VIEW \"{view}\" AS SELECT * FROM"
                f" read_parquet('{base}/*/*.parquet', hive_partitioning = true)"
            )
    return conn


def tabelas_do_lake() -> list[str]:
    """Nomes das views disponíveis (útil para notebooks se orientarem)."""
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal ORDER BY 1"
        ).fetchall()
    return [str(v) for (v,) in linhas]
