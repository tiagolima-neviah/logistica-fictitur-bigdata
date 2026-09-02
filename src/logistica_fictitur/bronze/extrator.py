"""Extrator bronze: staging Postgres → parquet, tabela a tabela, em streaming.

Regras da camada (invioláveis): o bronze é ESPELHO, não interpretação — nenhum
filtro, nenhum rename, nenhum cast além do que o driver Arrow preserva do
Postgres. O que o bronze acrescenta são só os metadados de carga
(`_extraido_em`, `_origem`), porque linhagem não é transformação.

Storage abstraído via fsspec (`LAKE_URL`): `data/lake` local por padrão,
`s3://...` (MinIO/nuvem) sem mudar uma linha de código. Layout:
`bronze/<schema>/<tabela>.parquet` + `bronze/_manifesto.json` por execução.

Uso: `uv run bronze-staging`. Ao final, verifica linha a linha as contagens
parquet × staging e sai com código 1 em qualquer divergência.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

import fsspec
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
from adbc_driver_postgresql import dbapi as adbc

from logistica_fictitur.config import dsn_staging, uri_staging, url_lake

SCHEMAS = ("cadastro", "fwm", "expedicao", "faturamento", "financeiro")


def _tabelas(conn: psycopg.Connection) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
            " WHERE table_schema = ANY(%s) AND table_type = 'BASE TABLE'"
            " ORDER BY 1, 2",
            (list(SCHEMAS),),
        )
        return [(str(s), str(t)) for s, t in cur.fetchall()]


def _com_metadados(lote: pa.RecordBatch, origem: str, instante: datetime) -> pa.RecordBatch:
    n = lote.num_rows
    colunas = list(lote.columns) + [
        pa.array([instante] * n, type=pa.timestamp("us", tz="UTC")),
        pa.array([origem] * n, type=pa.string()),
    ]
    nomes = lote.schema.names + ["_extraido_em", "_origem"]
    return pa.RecordBatch.from_arrays(colunas, names=nomes)


def _extrair_tabela(
    cur: Any, fs: fsspec.AbstractFileSystem, raiz: str, schema: str, tabela: str,
    instante: datetime,
) -> int:
    origem = f"{schema}.{tabela}"
    fs.makedirs(f"{raiz}/bronze/{schema}", exist_ok=True)
    destino = f"{raiz}/bronze/{schema}/{tabela}.parquet"
    cur.execute(f'SELECT * FROM {schema}."{tabela}"')  # noqa: S608 — nomes do catálogo
    leitor = cur.fetch_record_batch()  # streaming: o driver dita o tamanho dos lotes
    linhas = 0
    escritor: pq.ParquetWriter | None = None
    try:
        for lote in leitor:
            lote_final = _com_metadados(lote, origem, instante)
            if escritor is None:
                escritor = pq.ParquetWriter(
                    fs.open(destino, "wb"), lote_final.schema, compression="zstd"
                )
            escritor.write_batch(lote_final)
            linhas += lote_final.num_rows
        if escritor is None:  # tabela vazia: grava um parquet só com o esquema
            cur.execute(f'SELECT * FROM {schema}."{tabela}" LIMIT 0')  # noqa: S608
            esquema_base = cur.fetch_arrow_table().schema
            esquema = esquema_base.append(
                pa.field("_extraido_em", pa.timestamp("us", tz="UTC"))
            ).append(pa.field("_origem", pa.string()))
            with fs.open(destino, "wb") as f:
                pq.write_table(esquema.empty_table(), f, compression="zstd")
    finally:
        if escritor is not None:
            escritor.close()
    return linhas


def _contagens_staging(tabelas: list[tuple[str, str]]) -> dict[str, int]:
    saida: dict[str, int] = {}
    with psycopg.connect(dsn_staging()) as conn, conn.cursor() as cur:
        for schema, tabela in tabelas:
            cur.execute(f'SELECT count(*) FROM {schema}."{tabela}"')  # noqa: S608
            saida[f"{schema}.{tabela}"] = int(cur.fetchone()[0])  # type: ignore[index]
    return saida


def main() -> None:
    inicio = time.monotonic()
    instante = datetime.now(tz=UTC)
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    fs.makedirs(f"{raiz}/bronze", exist_ok=True)

    with psycopg.connect(dsn_staging()) as conn:
        tabelas = _tabelas(conn)
    print(f"Bronze: {len(tabelas)} tabelas do staging → {url_lake()}/bronze\n")

    extraidas: dict[str, int] = {}
    with adbc.connect(uri_staging()) as conexao, conexao.cursor() as cur:
        for schema, tabela in tabelas:
            n = _extrair_tabela(cur, fs, raiz, schema, tabela, instante)
            extraidas[f"{schema}.{tabela}"] = n
            print(f"  {schema}.{tabela}".ljust(42) + f"{n:>9} linhas")

    esperadas = _contagens_staging(tabelas)
    divergencias = {t: (esperadas[t], extraidas[t])
                    for t in esperadas if esperadas[t] != extraidas[t]}

    manifesto = {
        "extraido_em": instante.isoformat(),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "lake_url": url_lake(),
        "tabelas": extraidas,
        "total_linhas": sum(extraidas.values()),
        "verificacao": "OK" if not divergencias else f"DIVERGENTE: {divergencias}",
    }
    with fs.open(f"{raiz}/bronze/_manifesto.json", "w") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)

    print(f"\n{sum(extraidas.values())} linhas em {manifesto['duracao_s']}s.")
    if divergencias:
        print(f"VERIFICAÇÃO FALHOU — contagens divergentes: {divergencias}")
        sys.exit(1)
    print("Verificação de contagens bronze × staging: OK. Manifesto gravado.")


if __name__ == "__main__":
    main()
