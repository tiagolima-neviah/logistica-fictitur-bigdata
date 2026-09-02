"""Configuração 12-factor: tudo vem do ambiente (.env local, nunca versionado)."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def _staging() -> tuple[str, str, str, str, str]:
    load_dotenv()
    senha = os.environ.get("STAGING_PASSWORD")
    if not senha:
        raise RuntimeError("STAGING_PASSWORD ausente: copie .env.example para .env e preencha.")
    return (
        os.environ.get("STAGING_HOST", "localhost"),
        os.environ.get("STAGING_PORT", "5433"),
        os.environ.get("STAGING_DB", "db_fictitur"),
        os.environ.get("STAGING_USER", "fictitur"),
        senha,
    )


def dsn_staging() -> str:
    """DSN do Postgres de staging (formato libpq), das variáveis STAGING_*."""
    host, porta, banco, usuario, senha = _staging()
    return f"host={host} port={porta} dbname={banco} user={usuario} password={senha}"


def uri_staging() -> str:
    """URI do Postgres de staging (formato URL), para drivers como o ADBC."""
    host, porta, banco, usuario, senha = _staging()
    return f"postgresql://{usuario}:{senha}@{host}:{porta}/{banco}"


def url_lake() -> str:
    """Onde o lake vive, em URL fsspec: `file://...` local ou `s3://...` (12-factor).

    O padrão é o diretório `data/lake` do projeto (gitignorado). Trocar de
    storage é trocar UMA variável de ambiente, nunca o código.
    """
    load_dotenv()
    padrao = "data/lake"
    return os.environ.get("LAKE_URL", padrao)
