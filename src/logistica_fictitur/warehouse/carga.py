"""Carga do warehouse: gold (parquet) → Postgres dimensional, partição a partição.

O DuckDB faz a ponte: lê os parquet da gold e escreve no Postgres pela extensão
`postgres` (ATTACH), sem código de conversão de tipos. Dimensões são recriadas
inteiras (pequenas); fatos são carregadas POR PARTIÇÃO (ano), com o rito
idempotente `DELETE WHERE ano = X` + `INSERT`: recarregar um ano não toca nos
outros, e `DW_ANOS` escolhe quais anos subir (o mesmo script serve o container
local e um Neon).

Prestação de contas: cada partição confronta contagem no parquet × contagem no
Postgres; divergência derruba a carga. Ao final, mede o tamanho do banco (o
dado para decidir o que cabe no plano gratuito do destino).

Uso: `uv run carga-dw` (com a gold construída e o serviço `warehouse` no ar).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

import duckdb
import fsspec

from logistica_fictitur.config import anos_carga_dw, dsn_warehouse, url_lake
from logistica_fictitur.gold.dimensoes import DIMENSOES
from logistica_fictitur.gold.fatos import FATOS


def _n(conn: duckdb.DuckDBPyConnection, sql: str) -> int:
    linha = conn.execute(sql).fetchone()
    return int(linha[0]) if linha and linha[0] is not None else 0


def main() -> None:
    inicio = time.monotonic()
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    filtro = anos_carga_dw()

    conn = duckdb.connect()
    conn.execute("INSTALL postgres; LOAD postgres;")
    conn.execute(f"ATTACH '{dsn_warehouse()}' AS dw (TYPE postgres)")
    conn.execute("CREATE SCHEMA IF NOT EXISTS dw.dim")
    conn.execute("CREATE SCHEMA IF NOT EXISTS dw.fato")

    print("Warehouse: dimensões (recriadas inteiras)")
    for nome in DIMENSOES:
        arquivo = f"{raiz}/gold/dimensoes/{nome}.parquet"
        conn.execute(f"DROP TABLE IF EXISTS dw.dim.{nome}")
        conn.execute(f"CREATE TABLE dw.dim.{nome} AS SELECT * FROM read_parquet('{arquivo}')")
        print(f"  dim.{nome.ljust(20)} {_n(conn, f'SELECT count(*) FROM dw.dim.{nome}'):>9}")

    print("\nWarehouse: fatos, partição a partição (DELETE ano + INSERT)")
    manifesto: dict[str, dict[str, dict[str, int]]] = {}
    divergencias: list[str] = []
    for nome in FATOS:
        pasta = f"{raiz}/gold/fatos/{nome}"
        origem = f"read_parquet('{pasta}/*/*.parquet', hive_partitioning = true)"
        anos = [int(a) for (a,) in conn.execute(
            f"SELECT DISTINCT ano FROM {origem} ORDER BY 1").fetchall()]
        if filtro is not None:
            anos = [a for a in anos if a in filtro]
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS dw.fato.{nome} AS SELECT * FROM {origem} LIMIT 0"
        )
        manifesto[nome] = {}
        for ano in anos:
            conn.execute(f"DELETE FROM dw.fato.{nome} WHERE ano = {ano}")
            conn.execute(
                f"INSERT INTO dw.fato.{nome} SELECT * FROM {origem} WHERE ano = {ano}"
            )
            esperado = _n(conn, f"SELECT count(*) FROM {origem} WHERE ano = {ano}")
            carregado = _n(conn, f"SELECT count(*) FROM dw.fato.{nome} WHERE ano = {ano}")
            manifesto[nome][str(ano)] = {"parquet": esperado, "warehouse": carregado}
            if esperado != carregado:
                divergencias.append(f"{nome} ano={ano}: {esperado} × {carregado}")
        total = sum(v["warehouse"] for v in manifesto[nome].values())
        print(f"  fato.{nome.ljust(24)} {total:>9} linhas em {len(anos):>2} partições")

    # a medição roda DENTRO do Postgres (postgres_query), não no DuckDB
    tamanho = conn.execute(
        "SELECT * FROM postgres_query('dw',"
        " 'SELECT pg_size_pretty(pg_database_size(current_database()))')"
    ).fetchone()
    tamanho_txt = str(tamanho[0]) if tamanho else "?"

    registro = {
        "carregado_em": datetime.now(tz=UTC).isoformat(),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "anos_filtrados": filtro,
        "tamanho_banco": tamanho_txt,
        "particoes": manifesto,
        "veredito": "OK" if not divergencias else f"DIVERGENTE: {divergencias}",
    }
    fs.makedirs(f"{raiz}/gold", exist_ok=True)
    with fs.open(f"{raiz}/gold/_manifesto_warehouse.json", "w") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

    print(f"\nTamanho do warehouse: {tamanho_txt} · {registro['duracao_s']}s.")
    if divergencias:
        print(f"CARGA REPROVADA — partições divergentes: {divergencias}")
        sys.exit(1)
    print("Carga APROVADA: toda partição confere parquet × warehouse. Manifesto gravado.")


if __name__ == "__main__":
    main()
