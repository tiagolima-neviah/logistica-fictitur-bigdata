"""Régua de validação do staging: roda os checks contra o Postgres e dá o veredito.

Uso: `uv run regua-staging`. Saída: um relatório por check (observado × banda ×
veredito) e código de saída 1 se qualquer check reprovar — reprovou, regenera-se
a base. As bandas vivem em `bandas.py`, versionadas.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import psycopg

from logistica_fictitur.config import dsn_staging
from logistica_fictitur.validacao import bandas


@dataclass
class Resultado:
    check: str
    observado: str
    banda: str
    ok: bool


def _escalar(cur: psycopg.Cursor, sql: str) -> float | None:
    cur.execute(sql)
    linha = cur.fetchone()
    if linha is None or linha[0] is None:
        return None
    return float(linha[0])


def _avaliar(nome: str, valor: float | None, banda: bandas.Banda, fmt: str = "{:.4f}") -> Resultado:
    faixa = f"[{fmt.format(banda[0])} .. {fmt.format(banda[1])}]"
    if valor is None:
        return Resultado(nome, "sem dados", faixa, ok=False)
    return Resultado(nome, fmt.format(valor), faixa, banda[0] <= valor <= banda[1])


def _por_ano(
    cur: psycopg.Cursor, nome: str, sql: str, por_ano: dict[int, bandas.Banda], fmt: str
) -> list[Resultado]:
    cur.execute(sql)
    observados = {int(ano): float(valor) for ano, valor in cur.fetchall() if valor is not None}
    saida = []
    for ano, banda in sorted(por_ano.items()):
        saida.append(_avaliar(f"{nome} {ano}", observados.get(ano), banda, fmt))
    return saida


def executar(dsn: str) -> list[Resultado]:
    r: list[Resultado] = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        r += _por_ano(
            cur,
            "pedidos/mês",
            """
            SELECT extract(year FROM dt_solicitacao)::int AS ano,
                   count(*)::float
                   / greatest(count(DISTINCT date_trunc('month', dt_solicitacao)), 1)
            FROM fwm.pedido GROUP BY 1
            """,
            bandas.PEDIDOS_MES_POR_ANO,
            "{:.0f}",
        )
        r.append(
            _avaliar(
                "itens por pedido (média)",
                _escalar(
                    cur,
                    "SELECT count(*)::float / greatest(count(DISTINCT ss), 1) FROM fwm.pedido_item",
                ),
                bandas.ITENS_POR_PEDIDO,
                "{:.2f}",
            )
        )
        r.append(
            _avaliar(
                "total de linhas em pedido_item",
                _escalar(cur, "SELECT count(*) FROM fwm.pedido_item"),
                bandas.TOTAL_PEDIDO_ITEM,
                "{:.0f}",
            )
        )
        r += _por_ano(
            cur,
            "OTIF",
            """
            SELECT extract(year FROM p.dt_solicitacao)::int AS ano,
                   avg(CASE WHEN e.dt_entrega::date <= e.prazo_inicial_cliente
                            THEN 1.0 ELSE 0.0 END)
            FROM fwm.pedido p
            JOIN expedicao.entrega e USING (ss)
            WHERE e.dt_entrega IS NOT NULL
              AND e.prazo_inicial_cliente IS NOT NULL
              AND e.dt_entrega::date BETWEEN DATE '2019-01-01' AND DATE '2027-12-31'
            GROUP BY 1
            """,
            bandas.OTIF_POR_ANO,
            "{:.3f}",
        )
        r.append(
            _avaliar(
                "OTIF piso de cliente em 2020 (>=100 pedidos)",
                _escalar(
                    cur,
                    """
                    SELECT min(otif) FROM (
                        SELECT p.organizacao_id,
                               avg(CASE WHEN e.dt_entrega::date <= e.prazo_inicial_cliente
                                        THEN 1.0 ELSE 0.0 END) AS otif
                        FROM fwm.pedido p
                        JOIN expedicao.entrega e USING (ss)
                        WHERE extract(year FROM p.dt_solicitacao) = 2020
                          AND e.dt_entrega IS NOT NULL AND e.prazo_inicial_cliente IS NOT NULL
                          AND e.dt_entrega::date BETWEEN DATE '2019-01-01' AND DATE '2027-12-31'
                        GROUP BY 1 HAVING count(*) >= 100
                    ) t
                    """,
                ),
                bandas.OTIF_PISO_CLIENTE_2020,
                "{:.3f}",
            )
        )
        r.append(
            _avaliar(
                "share dos top 5 clientes em pedidos",
                _escalar(
                    cur,
                    """
                    SELECT sum(n)::float / greatest((SELECT count(*) FROM fwm.pedido), 1) FROM (
                        SELECT count(*) AS n FROM fwm.pedido GROUP BY organizacao_id
                        ORDER BY n DESC LIMIT 5
                    ) t
                    """,
                ),
                bandas.SHARE_TOP5_CLIENTES,
                "{:.3f}",
            )
        )
        for nome, codigo, banda in [
            ("presença da fase EA", "EA", bandas.PRESENCA_FASE_EA),
            ("incidência da fase DC", "DC", bandas.INCIDENCIA_FASE_DC),
            ("incidência da fase EX", "EX", bandas.INCIDENCIA_FASE_EX),
        ]:
            r.append(
                _avaliar(
                    nome,
                    _escalar(
                        cur,
                        f"""
                        SELECT count(DISTINCT pf.ss)::float
                               / greatest((SELECT count(*) FROM fwm.pedido), 1)
                        FROM fwm.pedido_fase pf
                        JOIN cadastro.fase f ON f.id = pf.fase_id
                        WHERE f.codigo = '{codigo}'
                        """,
                    ),
                    banda,
                    "{:.3f}",
                )
            )
        r.append(
            _avaliar(
                "fase atual EC com data de entrega",
                _escalar(
                    cur,
                    """
                    SELECT avg(CASE WHEN e.dt_entrega IS NOT NULL THEN 1.0 ELSE 0.0 END)
                    FROM fwm.pedido p
                    JOIN cadastro.fase f ON f.id = p.fase_id AND f.codigo = 'EC'
                    LEFT JOIN expedicao.entrega e ON e.ss = p.ss
                    """,
                ),
                bandas.EC_COM_DATA_ENTREGA,
                "{:.3f}",
            )
        )
        r.append(
            _avaliar(
                "sujeira: datas-sentinela na entrega",
                _escalar(
                    cur,
                    """
                    SELECT avg(CASE WHEN dt_entrega::date <= DATE '1900-01-01'
                                      OR dt_entrega::date >= DATE '2030-01-01'
                               THEN 1.0 ELSE 0.0 END)
                    FROM expedicao.entrega WHERE dt_entrega IS NOT NULL
                    """,
                ),
                bandas.SUJEIRA_DATA_SENTINELA_ENTREGA,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "sujeira: agendamento sem chegada",
                _escalar(
                    cur,
                    "SELECT avg(CASE WHEN dt_chegada IS NULL THEN 1.0 ELSE 0.0 END)"
                    " FROM fwm.agendamento",
                ),
                bandas.SUJEIRA_AGENDAMENTO_SEM_CHEGADA,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "sujeira: item sem valor unitário",
                _escalar(
                    cur,
                    "SELECT avg(CASE WHEN valor_unitario IS NULL THEN 1.0 ELSE 0.0 END)"
                    " FROM cadastro.item",
                ),
                bandas.SUJEIRA_ITEM_SEM_VALOR,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "pedidos sem nenhum item",
                _escalar(
                    cur,
                    """
                    SELECT avg(CASE WHEN pi.ss IS NULL THEN 1.0 ELSE 0.0 END)
                    FROM fwm.pedido p
                    LEFT JOIN (SELECT DISTINCT ss FROM fwm.pedido_item) pi USING (ss)
                    """,
                ),
                bandas.PEDIDO_SEM_ITEM,
                "{:.4f}",
            )
        )
        r.append(
            _avaliar(
                "MC% transporte",
                _escalar(
                    cur,
                    """
                    WITH taxa AS (
                        SELECT coalesce((SELECT valor FROM financeiro.parametro_financeiro
                                         WHERE chave = 'taxa_imposto_faturamento'
                                         ORDER BY vigencia_inicio DESC LIMIT 1), 0.0673) AS v
                    ), agg AS (
                        SELECT sum(valor_frete_icms) AS receita,
                               sum(valor_frete_icms - valor_frete) AS icms
                        FROM faturamento.fatura_frete
                    ), custo AS (
                        SELECT coalesce(sum(valor), 0) AS cv FROM financeiro.custo_operacao
                        WHERE categoria IN ('CUSTO_FRETE', 'DEV_REENTREGA')
                    )
                    SELECT CASE WHEN agg.receita > 0 THEN
                        (agg.receita - agg.receita * taxa.v - agg.icms - custo.cv) / agg.receita
                    END
                    FROM agg, taxa, custo
                    """,
                ),
                bandas.MC_PCT_TRANSPORTE,
                "{:.3f}",
            )
        )
        r.append(
            _avaliar(
                "MC% armazenagem",
                _escalar(
                    cur,
                    """
                    WITH taxa AS (
                        SELECT coalesce((SELECT valor FROM financeiro.parametro_financeiro
                                         WHERE chave = 'taxa_imposto_faturamento'
                                         ORDER BY vigencia_inicio DESC LIMIT 1), 0.0673) AS v
                    ), agg AS (
                        SELECT sum(valor_cobrado) AS receita FROM faturamento.fatura_armazenagem
                    ), custo AS (
                        SELECT coalesce(sum(s.m3_ocupado), 0)
                               * coalesce((SELECT valor FROM financeiro.parametro_financeiro
                                           WHERE chave = 'custo_m3_galpao'
                                           ORDER BY vigencia_inicio DESC LIMIT 1), 6.5) AS cv
                        FROM fwm.estoque_snapshot s
                        WHERE s.data = date_trunc('month', s.data)  -- fechamentos mensais
                    )
                    SELECT CASE WHEN agg.receita > 0 THEN
                        (agg.receita - agg.receita * taxa.v - custo.cv) / agg.receita
                    END
                    FROM agg, taxa, custo
                    """,
                ),
                bandas.MC_PCT_ARMAZENAGEM,
                "{:.3f}",
            )
        )
    return r


def main() -> None:
    resultados = executar(dsn_staging())
    largura = max(len(x.check) for x in resultados)
    reprovados = 0
    print(f"\nRégua de validação do staging — {len(resultados)} checks\n")
    for res in resultados:
        veredito = "OK   " if res.ok else "FALHA"
        if not res.ok:
            reprovados += 1
        print(f"  {veredito}  {res.check.ljust(largura)}  {res.observado:>12}  {res.banda}")
    print(f"\n{len(resultados) - reprovados} aprovados, {reprovados} reprovados.")
    if reprovados:
        print("Veredito: REGENERAR a base (banda estourada não se contorna).")
        sys.exit(1)
    print("Veredito: staging APROVADO pela régua.")


if __name__ == "__main__":
    main()
