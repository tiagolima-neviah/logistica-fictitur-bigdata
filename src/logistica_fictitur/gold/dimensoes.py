"""G1 — Dimensões conformadas do star schema (Kimball: uma dimensão, todos os marts).

Cada dimensão nasce da SILVER (nunca do bronze: a gold só enxerga dado
conformado) e é única para todos os fatos: é o que garante, por construção,
que qualquer relatório pendurado nelas conte a mesma história. Chaves
substitutas (sk_*) são as chaves naturais da silver, estáveis por origem.
"""

from __future__ import annotations

# nome do parquet -> consulta sobre as views silver_* do lake
DIMENSOES: dict[str, str] = {
    "dim_data": """
        SELECT cast(strftime(d.dia, '%Y%m%d') AS int) AS sk_data,
               d.dia::date AS data,
               extract(year FROM d.dia)::int AS ano,
               extract(month FROM d.dia)::int AS mes,
               strftime(d.dia, '%Y-%m') AS ano_mes,
               extract(quarter FROM d.dia)::int AS trimestre,
               extract(isodow FROM d.dia)::int AS dia_semana_iso,
               extract(isodow FROM d.dia) IN (6, 7) AS fl_fim_de_semana
        FROM (SELECT unnest(generate_series(DATE '2019-01-01', DATE '2027-12-31',
                                            INTERVAL 1 DAY)) AS dia) d
        UNION ALL
        -- membro especial (Kimball): data inválida/desconhecida. Fatos com data
        -- anulada pela silver apontam para cá em vez de sumir ou contaminar anos reais.
        SELECT -1, NULL, -1, NULL, 'inválida', NULL, NULL, NULL
    """,
    "dim_cliente": """
        SELECT id AS sk_cliente, sigla, nome_fantasia, porte, segmento,
               fl_entrega_agendada, otif_contratual,
               dt_inicio_contrato, dt_cancelamento, ativo
        FROM silver_cadastro_organizacao
        WHERE tipo_parceria = 'CLIENTE'
    """,
    "dim_item": """
        SELECT i.id AS sk_item, i.organizacao_id AS sk_cliente, o.sigla AS sigla_cliente,
               i.cod_item, i.descricao, i.grupo, i.subgrupo, i.marca, i.categoria,
               i.peso_kg,
               i.altura_cm * i.largura_cm * i.comprimento_cm / 1000000.0 AS m3_unitario,
               i.multiplo_saida, i.valor_unitario, i.fl_sem_valor_unitario
        FROM silver_cadastro_item i
        JOIN silver_cadastro_organizacao o ON o.id = i.organizacao_id
    """,
    "dim_geografia": """
        SELECT m.id AS sk_geografia, m.nome AS cidade, m.uf, u.nome AS nome_uf,
               u.regiao_geografica, r.nome AS regiao_comercial
        FROM silver_cadastro_municipio m
        JOIN silver_cadastro_uf u ON u.sigla = m.uf
        LEFT JOIN silver_cadastro_regiao r ON r.id = m.regiao_id
    """,
    "dim_modalidade": """
        SELECT id AS sk_modalidade, codigo, descricao FROM silver_cadastro_modalidade
    """,
    "dim_fase": """
        SELECT id AS sk_fase, codigo, nome, ordem, fl_esporadica FROM silver_cadastro_fase
    """,
    "dim_transportador": """
        SELECT id AS sk_transportador, razao_social FROM silver_cadastro_transportador
    """,
    "dim_galpao": """
        SELECT g.id AS sk_galpao, g.codigo, g.descricao,
               o.sigla AS sigla_dona, o.tipo_parceria AS tipo_dona,
               m.nome AS cidade, m.uf
        FROM silver_cadastro_galpao g
        JOIN silver_cadastro_organizacao o ON o.id = g.organizacao_id
        JOIN silver_cadastro_endereco e ON e.id = g.endereco_id
        JOIN silver_cadastro_municipio m ON m.id = e.municipio_id
    """,
    "dim_motivo_atraso": """
        SELECT id AS sk_motivo_atraso, descricao FROM silver_expedicao_motivo_atraso
    """,
    # --- dimensões pedidas pela matriz de barramento (docs/09) ---
    "dim_tipo_operacao": """
        SELECT * FROM (VALUES
            (1, 'TRANSPORTE', 'Frete de entrega'),
            (2, 'ARMAZENAGEM', 'Cobrança mensal de armazenagem'),
            (3, 'COLETA', 'Coleta na origem'),
            (4, 'POSITIVACAO', 'Serviço em loja'),
            (5, 'SERVICO_COMPLEMENTAR', 'Montagem de kit e insumos')
        ) AS t(sk_tipo_operacao, codigo, descricao)
    """,
    "dim_veiculo": """
        SELECT row_number() OVER (ORDER BY tipo_veiculo) AS sk_veiculo, tipo_veiculo
        FROM (
            SELECT DISTINCT tipo_veiculo FROM silver_expedicao_minuta
            WHERE tipo_veiculo IS NOT NULL
            UNION
            SELECT DISTINCT tipo_veiculo FROM silver_fwm_agendamento
            WHERE tipo_veiculo IS NOT NULL
        )
    """,
    "dim_faixa_peso": """
        SELECT * FROM (VALUES
            (1, 'até 30 kg',          0,    30),
            (2, '30 a 100 kg',       30,   100),
            (3, '100 a 300 kg',     100,   300),
            (4, '300 a 1.000 kg',   300,  1000),
            (5, 'acima de 1.000 kg', 1000, NULL)
        ) AS t(sk_faixa_peso, faixa, peso_min, peso_max)
    """,
    "dim_fornecedor": """
        SELECT row_number() OVER (ORDER BY fornecedor) AS sk_fornecedor, fornecedor
        FROM (SELECT DISTINCT fornecedor FROM silver_fwm_agendamento
              WHERE fornecedor IS NOT NULL)
    """,
    "dim_meta_frete": """
        SELECT m.id AS sk_meta_frete, m.regiao_id, r.nome AS regiao_comercial,
               m.tipo_destino, m.target_rs_kg
        FROM silver_cadastro_meta_frete m
        JOIN silver_cadastro_regiao r ON r.id = m.regiao_id
    """,
}
