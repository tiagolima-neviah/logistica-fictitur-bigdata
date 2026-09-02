"""Régua da gold: consistência interna do star schema (docs/09, decisão P2).

A gold não é comparada com nenhuma referência externa: ela precisa ser
coerente consigo mesma e com as camadas abaixo. Três famílias de checks:
(1) conservação: contagens e somas das fatos batem com a silver;
(2) integridade dimensional: toda chave sk_* obrigatória resolve na dimensão;
(3) coerência de indicadores: OTIF e margens apurados na gold caem nas mesmas
bandas da régua do staging (a história sobrevive às camadas).

Uso: `uv run regua-gold`. Exit 1 em qualquer reprovação.
"""

from __future__ import annotations

import sys

import duckdb

from logistica_fictitur.lake import conectar
from logistica_fictitur.validacao import bandas
from logistica_fictitur.validacao.regua import Resultado, _avaliar


def _num(conn: duckdb.DuckDBPyConnection, sql: str) -> float | None:
    linha = conn.execute(sql).fetchone()
    return None if linha is None or linha[0] is None else float(linha[0])


def _igual(conn: duckdb.DuckDBPyConnection, nome: str, a: str, b: str) -> Resultado:
    va, vb = _num(conn, a), _num(conn, b)
    ok = va is not None and vb is not None and abs(va - vb) < 0.5
    return Resultado(nome, f"{va:.0f} vs {vb:.0f}" if va is not None and vb is not None
                     else "sem dados", "iguais", ok)


def _resolve(conn: duckdb.DuckDBPyConnection, fato: str, sk: str, dim: str,
             sk_dim: str) -> Resultado:
    taxa = _num(conn, f"""
        SELECT avg(CASE WHEN d.{sk_dim} IS NOT NULL THEN 1.0 ELSE 0.0 END)
        FROM gold_fatos_{fato} f
        LEFT JOIN gold_dimensoes_{dim} d ON d.{sk_dim} = f.{sk}
    """)
    return _avaliar(f"{fato}.{sk} → {dim}", taxa, (1.0, 1.0), "{:.4f}")


def executar() -> list[Resultado]:
    r: list[Resultado] = []
    conn = conectar()

    # (1) conservação silver → gold
    r.append(_igual(conn, "ft_tracking: linhas = itens de pedido da silver",
                    "SELECT count(*) FROM gold_fatos_ft_tracking",
                    "SELECT count(*) FROM silver_fwm_pedido_item"))
    r.append(_igual(conn, "ft_tracking: pedidos distintos = pedidos da silver",
                    "SELECT count(DISTINCT ss) FROM gold_fatos_ft_tracking",
                    "SELECT count(*) FROM silver_fwm_pedido"))
    r.append(_igual(conn, "ft_frete: receita = faturas de frete da silver",
                    "SELECT round(sum(valor_frete_icms)) FROM gold_fatos_ft_frete",
                    "SELECT round(sum(valor_frete_icms)) FROM silver_faturamento_fatura_frete"))
    r.append(_igual(conn, "ft_estoque_foto: linhas = fotos da silver",
                    "SELECT count(*) FROM gold_fatos_ft_estoque_foto",
                    "SELECT count(*) FROM silver_fwm_estoque_snapshot"))
    r.append(_igual(conn, "ft_mc_operacao: receita de transporte = faturas de frete",
                    "SELECT round(sum(receita)) FROM gold_fatos_ft_mc_operacao"
                    " WHERE sk_tipo_operacao = 1",
                    "SELECT round(sum(valor_frete_icms)) FROM silver_faturamento_fatura_frete"))
    r.append(_igual(conn, "ft_mc_operacao: receita de armazenagem = faturas de armazenagem",
                    "SELECT round(sum(receita)) FROM gold_fatos_ft_mc_operacao"
                    " WHERE sk_tipo_operacao = 2",
                    "SELECT round(sum(valor_cobrado)) FROM silver_faturamento_fatura_armazenagem"))

    # (2) integridade dimensional (chaves obrigatórias)
    for fato, sk, dim, sk_dim in [
        ("ft_tracking", "sk_cliente", "dim_cliente", "sk_cliente"),
        ("ft_tracking", "sk_item", "dim_item", "sk_item"),
        ("ft_tracking", "sk_data_solicitacao", "dim_data", "sk_data"),
        ("ft_estoque_foto", "sk_galpao", "dim_galpao", "sk_galpao"),
        ("ft_frete", "sk_faixa_peso", "dim_faixa_peso", "sk_faixa_peso"),
        ("ft_frete", "sk_meta_frete", "dim_meta_frete", "sk_meta_frete"),
        ("ft_mc_operacao", "sk_tipo_operacao", "dim_tipo_operacao", "sk_tipo_operacao"),
        ("ft_mc_operacao", "sk_competencia", "dim_data", "sk_data"),
    ]:
        r.append(_resolve(conn, fato, sk, dim, sk_dim))

    # (3) coerência de indicadores: a história sobrevive às camadas
    otif = conn.execute("""
        SELECT d.ano,
               count(DISTINCT t.ss) FILTER (WHERE t.fl_no_prazo) * 1.0
               / count(DISTINCT t.ss) FILTER (WHERE t.fl_entregue
                                              AND NOT t.fl_data_entrega_invalida)
        FROM gold_fatos_ft_tracking t
        JOIN gold_dimensoes_dim_data d ON d.sk_data = t.sk_data_prazo_cliente
        GROUP BY 1
    """).fetchall()
    observado = {int(a): float(v) for a, v in otif if v is not None}
    for ano, banda in sorted(bandas.OTIF_POR_ANO.items()):
        r.append(_avaliar(f"OTIF gold (eixo da promessa) {ano}", observado.get(ano),
                          banda, "{:.3f}"))
    r.append(_avaliar(
        "MC% transporte (ft_mc_operacao)",
        _num(conn, "SELECT sum(mc) / sum(receita) FROM gold_fatos_ft_mc_operacao"
                   " WHERE sk_tipo_operacao = 1"),
        bandas.MC_PCT_TRANSPORTE, "{:.3f}"))
    r.append(_avaliar(
        "MC% armazenagem (ft_mc_operacao)",
        _num(conn, "SELECT sum(mc) / sum(receita) FROM gold_fatos_ft_mc_operacao"
                   " WHERE sk_tipo_operacao = 2"),
        bandas.MC_PCT_ARMAZENAGEM, "{:.3f}"))
    r.append(_avaliar(
        "partições: ft_tracking cobre 2020..2026",
        _num(conn, "SELECT count(DISTINCT ano) FROM gold_fatos_ft_tracking"),
        (7, 7), "{:.0f}"))
    r.append(_avaliar(
        "partições: ft_mc_operacao só em 2020..2027 ou no membro 'inválida' (-1)",
        _num(conn, "SELECT count(*) FROM gold_fatos_ft_mc_operacao"
                   " WHERE ano NOT BETWEEN 2020 AND 2027 AND ano <> -1"),
        (0, 0), "{:.0f}"))
    r.append(_avaliar(
        "FIN-03: linhas no membro 'inválida' = custos anulados pela silver",
        _num(conn, "SELECT count(*) FROM gold_fatos_ft_mc_operacao WHERE ano = -1"),
        (73, 73), "{:.0f}"))
    return r


def main() -> None:
    resultados = executar()
    largura = max(len(x.check) for x in resultados)
    reprovados = sum(1 for x in resultados if not x.ok)
    print(f"\nRégua da gold — {len(resultados)} checks de consistência interna\n")
    for res in resultados:
        print(f"  {'OK   ' if res.ok else 'FALHA'}  {res.check.ljust(largura)}"
              f"  {res.observado:>22}  {res.banda}")
    print(f"\n{len(resultados) - reprovados} aprovados, {reprovados} reprovados.")
    if reprovados:
        print("Veredito: gold REPROVADA — reconstruir depois de corrigir a fonte da divergência.")
        sys.exit(1)
    print("Veredito: gold APROVADA (coerente com a silver e com a história).")


if __name__ == "__main__":
    main()
