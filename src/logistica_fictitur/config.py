"""Configuração 12-factor: tudo vem do ambiente (.env local, nunca versionado)."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def dsn_staging() -> str:
    """DSN do Postgres de staging, montado a partir das variáveis STAGING_*."""
    load_dotenv()
    host = os.environ.get("STAGING_HOST", "localhost")
    porta = os.environ.get("STAGING_PORT", "5433")
    banco = os.environ.get("STAGING_DB", "db_fictitur")
    usuario = os.environ.get("STAGING_USER", "fictitur")
    senha = os.environ.get("STAGING_PASSWORD")
    if not senha:
        raise RuntimeError("STAGING_PASSWORD ausente: copie .env.example para .env e preencha.")
    return f"host={host} port={porta} dbname={banco} user={usuario} password={senha}"
