"""Configuração 12-factor: tudo vem do ambiente (.env local, nunca versionado)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# A raiz do projeto, derivada do próprio pacote (src/logistica_fictitur/ → 2 níveis
# acima). É o que torna caminhos relativos independentes do diretório de quem chama:
# um notebook em notebooks/ e um script na raiz enxergam o MESMO lake e o MESMO .env.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def _carregar_env() -> None:
    load_dotenv(RAIZ_PROJETO / ".env")


def _staging() -> tuple[str, str, str, str, str]:
    _carregar_env()
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


def dsn_warehouse() -> str:
    """DSN libpq do warehouse multidimensional (variáveis DW_*; Neon = trocar host/senha)."""
    _carregar_env()
    senha = os.environ.get("DW_PASSWORD")
    if not senha:
        raise RuntimeError("DW_PASSWORD ausente: defina no .env (ver .env.example).")
    return (
        f"host={os.environ.get('DW_HOST', 'localhost')} "
        f"port={os.environ.get('DW_PORT', '5434')} "
        f"dbname={os.environ.get('DW_DB', 'dw_fictitur')} "
        f"user={os.environ.get('DW_USER', 'fictitur')} password={senha}"
    )


def anos_carga_dw() -> list[int] | None:
    """Partições a carregar no warehouse (DW_ANOS='2024,2025'); None = todas."""
    _carregar_env()
    bruto = os.environ.get("DW_ANOS", "").strip()
    return [int(a) for a in bruto.split(",") if a.strip()] or None


def url_lake() -> str:
    """Onde o lake vive, em URL fsspec: `file://...` local ou `s3://...` (12-factor).

    O padrão é o diretório `data/lake` do projeto (gitignorado). Trocar de
    storage é trocar UMA variável de ambiente, nunca o código. Caminho local
    RELATIVO é ancorado na raiz do projeto, para funcionar igual num script na
    raiz e num notebook em `notebooks/` (o cwd de quem chama não importa).
    """
    _carregar_env()
    url = os.environ.get("LAKE_URL", "data/lake")
    if "://" not in url and not Path(url).is_absolute():
        return str(RAIZ_PROJETO / url)
    return url
