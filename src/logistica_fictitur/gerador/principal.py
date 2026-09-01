"""Entrada do gerador: roda as etapas na ordem. Uso: `uv run gerador-staging`.

Idempotente: se o staging já tem organizações, aborta com instrução de reset
(o reset é `docker compose down -v && up`, que recria o banco vazio pelo DDL).
"""

from __future__ import annotations

import psycopg

from logistica_fictitur.config import dsn_staging
from logistica_fictitur.gerador.etapa1_cadastro import MundoCadastral
from logistica_fictitur.gerador.etapa2_itens_tarifas import CatalogoComercial
from logistica_fictitur.gerador.etapa3_arco_pedidos import ArcoPedidos
from logistica_fictitur.gerador.etapa4_estoque_armazenagem import EstoqueArmazenagem

Etapa = MundoCadastral | CatalogoComercial | ArcoPedidos | EstoqueArmazenagem


def _rodar(nome: str, etapa: Etapa) -> None:
    if etapa.ja_populado():
        print(f"{nome}: já populada, pulando.")
        return
    print(f"{nome}...")
    for tabela, n in etapa.executar().items():
        print(f"  {tabela.ljust(22)} {n:>8}")


def main() -> None:
    with psycopg.connect(dsn_staging()) as conn:
        _rodar("Etapa 1/4 — mundo cadastral", MundoCadastral(conn))
        _rodar("Etapa 2/4 — catálogo comercial e réguas de prazo", CatalogoComercial(conn))
        _rodar("Etapa 3/4 — arco operacional de pedidos 2020-2026", ArcoPedidos(conn))
        _rodar("Etapa 4/4 — recebimento, estoque e armazenagem", EstoqueArmazenagem(conn))
    print("\nStaging completo. Valide com: uv run regua-staging")
    print("Para regenerar do zero: cd staging && docker compose --env-file ../.env"
          " down -v && docker compose --env-file ../.env up -d")


if __name__ == "__main__":
    main()
