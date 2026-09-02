"""Transformador silver: aplica as regras do catálogo aprovado (docs/07) e presta contas.

O que esta camada faz, e só isso: para cada tabela do bronze, grava a versão
silver em parquet; nas seis tabelas alcançadas por regras, aplica as
conformações aprovadas (na ordem da Seção 3 do catálogo: valores impossíveis
primeiro, depois flags, depois seleção de colunas); nas demais, passa 1:1.
Nada se apaga, nada se preenche, nada se reordena.

Prestação de contas: cada regra tem a MEDIDA ESPERADA congelada do catálogo;
o executado é confrontado com o prometido e qualquer divergência derruba a
execução com erro (catálogo só muda com nova aprovação). Relatório em
`silver/_auditoria.json`.

Uso: `uv run silver-staging` (com o bronze extraído).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime

import duckdb
import fsspec

from logistica_fictitur.config import url_lake
from logistica_fictitur.lake import conectar

# As medidas aprovadas no catálogo (docs/07, base de 2026-09-02). Se o bronze for
# regenerado com outra semente, estas medidas mudam JUNTO com uma nova aprovação.
ESPERADO = {
    "CAD-02 itens marcados sem valor unitário": 112,
    "CAD-03 colunas 100% nulas removidas de item": 4,
    "PED-01 entregas com data impossível anulada": 5_126,
    "PED-02 pedidos marcados timeline inconsistente": 26_262,
    "EST-01 lotes com validade absurda anulada": 47,
    "EST-03 itens marcados razão não concilia": 1_983,
    "FIN-01 faturas marcadas frete simbólico": 124_108,
}

JANELA_PLAUSIVEL = "BETWEEN DATE '2019-01-01' AND DATE '2027-12-31'"


def _escalar(conn: duckdb.DuckDBPyConnection, consulta: str) -> int:
    linha = conn.execute(consulta).fetchone()
    return int(linha[0]) if linha and linha[0] is not None else 0


def _copiar(conn: duckdb.DuckDBPyConnection, consulta: str, destino: str) -> int:
    conn.execute(
        f"COPY ({consulta}) TO '{destino}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    return _escalar(conn, f"SELECT count(*) FROM read_parquet('{destino}')")


def _preparar_apoio(conn: duckdb.DuckDBPyConnection) -> None:
    """Conjuntos auxiliares que as regras usam (calculados uma vez)."""
    conn.execute(
        """
        CREATE TEMP TABLE apoio_timeline AS
        SELECT DISTINCT pf.ss FROM bronze_fwm_pedido_fase pf
        JOIN bronze_cadastro_fase f ON f.id = pf.fase_id
        QUALIFY pf.dt_entrada < lag(pf.dt_entrada)
            OVER (PARTITION BY pf.ss ORDER BY f.ordem)
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE apoio_razao AS
        WITH razao AS (
            SELECT item_id, sum(quantidade) AS saldo_teorico
            FROM bronze_fwm_movimento_estoque GROUP BY 1
        ),
        foto AS (
            SELECT item_id, sum(qtde_saldo) AS saldo_foto
            FROM bronze_fwm_estoque_snapshot
            WHERE data = (SELECT max(data) FROM bronze_fwm_estoque_snapshot)
            GROUP BY 1
        )
        SELECT r.item_id FROM razao r JOIN foto f USING (item_id)
        WHERE r.saldo_teorico <> f.saldo_foto
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE apoio_colunas_mortas AS
        SELECT column_name FROM (SUMMARIZE SELECT * FROM bronze_cadastro_item)
        WHERE null_percentage = 100
        """
    )


def _regras(conn: duckdb.DuckDBPyConnection) -> dict[str, tuple[str, int]]:
    """Por tabela transformada: (SELECT da silver, medida executada da regra)."""
    colunas_mortas = [str(c) for (c,) in conn.execute(
        "SELECT column_name FROM apoio_colunas_mortas").fetchall()]
    colunas_item = [str(c) for (c,) in conn.execute(
        "SELECT column_name FROM (DESCRIBE bronze_cadastro_item)").fetchall()]
    vivas = ", ".join(f'"{c}"' for c in colunas_item if c not in colunas_mortas)

    return {
        "fwm/pedido": (
            """
            SELECT p.*, (t.ss IS NOT NULL) AS fl_timeline_inconsistente
            FROM bronze_fwm_pedido p
            LEFT JOIN apoio_timeline t USING (ss)
            """,
            _escalar(conn, "SELECT count(*) FROM apoio_timeline"),
        ),
        "expedicao/entrega": (
            f"""
            SELECT * EXCLUDE (dt_entrega),
                   CASE WHEN dt_entrega::date {JANELA_PLAUSIVEL}
                        THEN dt_entrega END AS dt_entrega,
                   dt_entrega AS dt_entrega_original,
                   (dt_entrega IS NOT NULL
                    AND NOT dt_entrega::date {JANELA_PLAUSIVEL}) AS fl_data_entrega_invalida
            FROM bronze_expedicao_entrega
            """,
            _escalar(conn, f"""
                SELECT count(*) FROM bronze_expedicao_entrega
                WHERE dt_entrega IS NOT NULL
                  AND NOT dt_entrega::date {JANELA_PLAUSIVEL}"""),
        ),
        "cadastro/item": (
            f"""
            SELECT {vivas}, (valor_unitario IS NULL) AS fl_sem_valor_unitario
            FROM bronze_cadastro_item
            """,
            _escalar(conn,
                     "SELECT count(*) FROM bronze_cadastro_item WHERE valor_unitario IS NULL"),
        ),
        "fwm/lote": (
            """
            SELECT * EXCLUDE (dt_validade),
                   CASE WHEN dt_validade <= DATE '2040-01-01'
                        THEN dt_validade END AS dt_validade,
                   dt_validade AS dt_validade_original,
                   (dt_validade > DATE '2040-01-01') AS fl_validade_invalida
            FROM bronze_fwm_lote
            """,
            _escalar(conn,
                     "SELECT count(*) FROM bronze_fwm_lote WHERE dt_validade > DATE '2040-01-01'"),
        ),
        "fwm/movimento_estoque": (
            """
            SELECT m.*, (r.item_id IS NOT NULL) AS fl_razao_nao_concilia
            FROM bronze_fwm_movimento_estoque m
            LEFT JOIN apoio_razao r USING (item_id)
            """,
            _escalar(conn, "SELECT count(*) FROM apoio_razao"),
        ),
        "faturamento/fatura_frete": (
            """
            SELECT *, (valor_frete_icms <= 0.05) AS fl_frete_simbolico
            FROM bronze_faturamento_fatura_frete
            """,
            _escalar(conn, """
                SELECT count(*) FROM bronze_faturamento_fatura_frete
                WHERE valor_frete_icms <= 0.05"""),
        ),
    }


def main() -> None:
    inicio = time.monotonic()
    fs, raiz = fsspec.core.url_to_fs(url_lake())
    raiz = raiz.rstrip("/")
    conn = conectar()
    _preparar_apoio(conn)
    regras = _regras(conn)

    executado = {
        "CAD-02 itens marcados sem valor unitário": regras["cadastro/item"][1],
        "CAD-03 colunas 100% nulas removidas de item":
            _escalar(conn, "SELECT count(*) FROM apoio_colunas_mortas"),
        "PED-01 entregas com data impossível anulada": regras["expedicao/entrega"][1],
        "PED-02 pedidos marcados timeline inconsistente": regras["fwm/pedido"][1],
        "EST-01 lotes com validade absurda anulada": regras["fwm/lote"][1],
        "EST-03 itens marcados razão não concilia": regras["fwm/movimento_estoque"][1],
        "FIN-01 faturas marcadas frete simbólico": regras["faturamento/fatura_frete"][1],
    }

    # grava a silver: transformadas pelas regras + passagem 1:1 das demais
    bronzes = [str(v) for (v,) in conn.execute(
        "SELECT view_name FROM duckdb_views() WHERE view_name LIKE 'bronze_%'"
    ).fetchall()]
    total = 0
    print(f"Silver: {len(bronzes)} tabelas → {url_lake()}/silver\n")
    for view in sorted(bronzes):
        schema, tabela = view.removeprefix("bronze_").split("_", 1)
        alvo = f"{schema}/{tabela}"
        fs.makedirs(f"{raiz}/silver/{schema}", exist_ok=True)
        destino = f"{raiz}/silver/{schema}/{tabela}.parquet"
        consulta = regras[alvo][0] if alvo in regras else f'SELECT * FROM "{view}"'
        n = _copiar(conn, consulta, destino)
        total += n
        marca = "  [regra]" if alvo in regras else ""
        print(f"  {alvo}".ljust(40) + f"{n:>9} linhas{marca}")

    divergencias = {
        regra: {"esperado": ESPERADO[regra], "executado": executado[regra]}
        for regra in ESPERADO if ESPERADO[regra] != executado[regra]
    }
    auditoria = {
        "executado_em": datetime.now(tz=UTC).isoformat(),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "linhas_gravadas": total,
        "regras": {r: {"esperado_catalogo": ESPERADO[r], "executado": executado[r]}
                   for r in ESPERADO},
        "veredito": "APROVADO" if not divergencias else f"DIVERGENTE: {divergencias}",
    }
    with fs.open(f"{raiz}/silver/_auditoria.json", "w") as f:
        json.dump(auditoria, f, ensure_ascii=False, indent=2)

    print("\nPrestação de contas (executado × prometido no catálogo):")
    for regra in ESPERADO:
        ok = "OK   " if regra not in divergencias else "FALHA"
        print(f"  {ok} {regra.ljust(48)} {executado[regra]:>8} (esperado {ESPERADO[regra]})")
    print(f"\n{total} linhas gravadas em {auditoria['duracao_s']}s.")
    if divergencias:
        print("AUDITORIA REPROVADA: o executado diverge do catálogo aprovado.")
        sys.exit(1)
    print("Auditoria APROVADA: a silver fez o que o catálogo prometeu, nada além.")


if __name__ == "__main__":
    main()
