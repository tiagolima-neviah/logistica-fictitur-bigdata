-- db_fictitur: modelo relacional da Fictitur Logística (fonte que o staging espelha).
-- Ordem de execução: 00 → 05. Convenções: snake_case, FKs nomeadas, CHECKs para domínios.
-- O processo de carga incremental adiciona em cada tabela do staging as colunas de
-- controle (_carregado_em timestamptz, _origem text) — fora deste DDL de entidades.
-- Decisão 2026-09-01: NÃO existe schema de planilhas. Toda informação que no ambiente
-- real vivia em Excel de usuário tem origem no próprio sistema; planilha de usuário
-- não é fonte de dados, e o pipeline nasce do relacional.

CREATE SCHEMA IF NOT EXISTS cadastro;
CREATE SCHEMA IF NOT EXISTS fwm;
CREATE SCHEMA IF NOT EXISTS expedicao;
CREATE SCHEMA IF NOT EXISTS faturamento;
CREATE SCHEMA IF NOT EXISTS financeiro;
