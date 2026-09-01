"""Entrada do gerador: roda as etapas na ordem. Uso: `uv run gerador-staging`.

Idempotente: se o staging já tem organizações, aborta com instrução de reset
(o reset é `docker compose down -v && up`, que recria o banco vazio pelo DDL).
"""

from __future__ import annotations

import sys

import psycopg

from logistica_fictitur.config import dsn_staging
from logistica_fictitur.gerador.etapa1_cadastro import MundoCadastral


def main() -> None:
    with psycopg.connect(dsn_staging()) as conn:
        mundo = MundoCadastral(conn)
        if mundo.ja_populado():
            print("Staging já populado. Para regenerar do zero:")
            print("  cd staging && docker compose --env-file ../.env down -v && "
                  "docker compose --env-file ../.env up -d")
            sys.exit(2)
        print("Etapa 1/4 — mundo cadastral...")
        contagens = mundo.executar()
        for tabela, n in contagens.items():
            print(f"  cadastro: {tabela.ljust(20)} {n:>7}")
    print("\nEtapa 1 concluída. Próximas etapas (itens/tarifas, arco operacional,"
          " sujeira) em desenvolvimento.")


if __name__ == "__main__":
    main()
