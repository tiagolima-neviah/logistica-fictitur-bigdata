"""Bandas de aceite do staging sintético — o contrato que o gerador deve honrar.

Cada banda é (mínimo, máximo) inclusivo. As bandas são deliberadamente largas na
primeira versão e se estreitam por calibração conforme o gerador amadurece; todo
ajuste é versionado e aprovado, nunca silencioso. Fora da banda, a base é
REGENERADA, não contornada.
"""

from __future__ import annotations

Banda = tuple[float, float]

# --- Volumes -----------------------------------------------------------------

# Média de pedidos por mês em cada ano: crescimento ao longo do arco 2020-2026.
PEDIDOS_MES_POR_ANO: dict[int, Banda] = {
    2020: (6_000, 9_500),
    2021: (8_000, 11_500),
    2022: (9_000, 13_000),
    2023: (11_000, 15_000),
    2024: (13_000, 17_500),
    2025: (15_000, 19_500),
    2026: (16_000, 21_000),
}

ITENS_POR_PEDIDO: Banda = (3.0, 7.0)

# Maior fato do staging: itens de pedido acumulados no período inteiro.
TOTAL_PEDIDO_ITEM: Banda = (4_000_000, 9_000_000)

# --- Arco de indicadores (a história 2020-2026) ------------------------------

# OTIF geral por ano: percentual de pedidos entregues até o prazo prometido.
OTIF_POR_ANO: dict[int, Banda] = {
    2020: (0.75, 0.90),
    2021: (0.75, 0.90),
    2022: (0.75, 0.90),
    2023: (0.75, 0.90),
    2024: (0.80, 0.93),   # virada no 2º semestre
    2025: (0.93, 0.99),
    2026: (0.94, 0.99),
}

# Em 2020, o pior cliente relevante (>= 100 pedidos no ano) beira os 50%.
OTIF_PISO_CLIENTE_2020: Banda = (0.45, 0.62)

# Concentração de carteira: os 5 maiores clientes carregam a maior parte do volume.
SHARE_TOP5_CLIENTES: Banda = (0.50, 0.75)

# --- Fases do pedido ---------------------------------------------------------

# Todo pedido registra a fase EA (Em Análise); esporádicas têm incidência parcial.
PRESENCA_FASE_EA: Banda = (0.999, 1.0)
INCIDENCIA_FASE_DC: Banda = (0.60, 0.95)
INCIDENCIA_FASE_EX: Banda = (0.10, 0.90)

# Pedido cuja fase atual é EC (Entrega ao Cliente) precisa ter data de entrega.
EC_COM_DATA_ENTREGA: Banda = (0.99, 1.0)

# --- Catálogo de sujeira (taxas-alvo, propositais) ---------------------------

SUJEIRA_DATA_SENTINELA_ENTREGA: Banda = (0.001, 0.02)   # 1899-12-30 e futuros absurdos
SUJEIRA_AGENDAMENTO_SEM_CHEGADA: Banda = (0.05, 0.15)   # ref. real ~9,6%
SUJEIRA_ITEM_SEM_VALOR: Banda = (0.005, 0.03)           # furo de cobertura fiscal

# --- Integridade de negócio (o que FK não garante) ---------------------------

PEDIDO_SEM_ITEM: Banda = (0.0, 0.005)

# --- Margens (BI financeiro; calibração fina na 1ª rodada do gerador) --------

MC_PCT_TRANSPORTE: Banda = (0.35, 0.60)
MC_PCT_ARMAZENAGEM: Banda = (0.00, 0.15)
