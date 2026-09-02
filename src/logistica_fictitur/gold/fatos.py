"""G3 — Fatos do Painel 1 (Gestão de Materiais), no grão declarado na matriz (docs/09).

Toda fato nasce da SILVER, pendura nas dimensões conformadas por chaves `sk_*`
e carrega a coluna `ano` (partição hive no lake). Datas com papéis: a mesma
`dim_data` entra como solicitação, PRAZO PROMETIDO AO CLIENTE, entrega etc.
Medidas são base (somáveis ou contáveis); comparativos e rankings ficam na
apresentação.
"""

from __future__ import annotations

DATA_CORRENTE = "DATE '2026-09-01'"  # o "hoje" do universo do caso


def _sk(col: str) -> str:
    return f"cast(strftime({col}, '%Y%m%d') AS int)"


M3_ITEM = "(i.altura_cm * i.largura_cm * i.comprimento_cm / 1000000.0)"

FATOS: dict[str, str] = {
    "ft_tracking": f"""
        WITH minuta_do_pedido AS (
            SELECT mp.ss, min(m.transportador_id) AS transportador_id,
                   min(m.tipo_veiculo) AS tipo_veiculo
            FROM silver_expedicao_minuta_pedido mp
            JOIN silver_expedicao_minuta m ON m.id = mp.minuta_id
            GROUP BY 1
        ),
        ocorrencias AS (
            SELECT ss,
                   bool_or(tipo = 'OCORRENCIA') AS fl_ocorrencia,
                   bool_or(tipo = 'REENTREGA')  AS fl_reentrega,
                   bool_or(tipo = 'DEVOLUCAO')  AS fl_devolucao
            FROM silver_expedicao_ocorrencia_entrega GROUP BY 1
        )
        SELECT {_sk('p.dt_solicitacao')}            AS sk_data_solicitacao,
               {_sk('e.prazo_inicial_cliente')}     AS sk_data_prazo_cliente,
               {_sk('e.prazo_interno')}             AS sk_data_prazo_interno,
               {_sk('e.dt_entrega')}                AS sk_data_entrega,
               p.organizacao_id                     AS sk_cliente,
               pi.item_id                           AS sk_item,
               en.municipio_id                      AS sk_geografia,
               p.modalidade_id                      AS sk_modalidade,
               md.transportador_id                  AS sk_transportador,
               v.sk_veiculo                         AS sk_veiculo,
               e.motivo_atraso_id                   AS sk_motivo_atraso,
               p.ss                                 AS ss,
               pi.quantidade                        AS quantidade,
               pi.valor_total                       AS valor_item,
               pi.quantidade * i.peso_kg            AS peso_kg,
               pi.quantidade * {M3_ITEM}            AS m3,
               (e.dt_entrega IS NOT NULL)                       AS fl_entregue,
               (e.dt_entrega::date <= e.prazo_inicial_cliente)  AS fl_no_prazo,
               coalesce(o.fl_ocorrencia, false)                 AS fl_ocorrencia,
               coalesce(o.fl_reentrega, false)                  AS fl_reentrega,
               coalesce(o.fl_devolucao, false)                  AS fl_devolucao,
               p.fl_timeline_inconsistente,
               coalesce(e.fl_data_entrega_invalida, false)      AS fl_data_entrega_invalida,
               greatest(0, date_diff('day', e.prazo_inicial_cliente, e.dt_entrega::date))
                                                    AS dias_atraso,
               extract(year FROM p.dt_solicitacao)::int AS ano
        FROM silver_fwm_pedido_item pi
        JOIN silver_fwm_pedido p              ON p.ss = pi.ss
        JOIN silver_cadastro_item i           ON i.id = pi.item_id
        LEFT JOIN silver_expedicao_entrega e  ON e.ss = p.ss
        LEFT JOIN silver_cadastro_endereco en ON en.id = p.endereco_entrega_id
        LEFT JOIN minuta_do_pedido md         ON md.ss = p.ss
        LEFT JOIN gold_dimensoes_dim_veiculo v ON v.tipo_veiculo = md.tipo_veiculo
        LEFT JOIN ocorrencias o               ON o.ss = p.ss
    """,
    "ft_estoque_foto": f"""
        SELECT {_sk('s.data')}                       AS sk_data_foto,
               i.organizacao_id                     AS sk_cliente,
               s.item_id                            AS sk_item,
               s.galpao_id                          AS sk_galpao,
               s.qtde_saldo, s.m3_ocupado, s.valor_material, s.valor_danificado,
               s.dias_sem_movimento,
               s.m3_ocupado * pr.custo_m3           AS custo_armazenagem,
               i.fl_sem_valor_unitario,
               (s.valor_danificado > 0)             AS fl_danificado,
               extract(year FROM s.data)::int       AS ano
        FROM silver_fwm_estoque_snapshot s
        JOIN silver_cadastro_item i ON i.id = s.item_id
        CROSS JOIN (SELECT valor AS custo_m3 FROM silver_financeiro_parametro_financeiro
                    WHERE chave = 'custo_m3_galpao'
                    ORDER BY vigencia_inicio DESC LIMIT 1) pr
    """,
    "ft_recebimento": f"""
        SELECT {_sk('ri.dt_recebimento')}            AS sk_data_recebimento,
               a.organizacao_id                     AS sk_cliente,
               ri.item_id                           AS sk_item,
               ri.galpao_destino_id                 AS sk_galpao,
               f.sk_fornecedor                      AS sk_fornecedor,
               ri.ordem_recebimento_id              AS ordem_recebimento,
               ri.quantidade,
               ri.quantidade * i.valor_unitario     AS valor_recebido,
               ri.quantidade * {M3_ITEM}            AS m3_recebida,
               date_diff('day', ri.dt_transporte, ri.dt_recebimento)  AS dias_recebimento,
               date_diff('day', ri.dt_recebimento, ri.dt_subida_cota) AS dias_cota,
               i.fl_sem_valor_unitario,
               extract(year FROM ri.dt_recebimento)::int AS ano
        FROM silver_fwm_recebimento_item ri
        JOIN silver_fwm_ordem_recebimento orr ON orr.id = ri.ordem_recebimento_id
        JOIN silver_fwm_agendamento a         ON a.id = orr.agendamento_id
        JOIN silver_cadastro_item i           ON i.id = ri.item_id
        LEFT JOIN gold_dimensoes_dim_fornecedor f ON f.fornecedor = a.fornecedor
    """,
    "ft_agendamento": f"""
        WITH valor AS (
            SELECT orr.agendamento_id, sum(ri.quantidade * i.valor_unitario) AS valor_recebido
            FROM silver_fwm_recebimento_item ri
            JOIN silver_fwm_ordem_recebimento orr ON orr.id = ri.ordem_recebimento_id
            JOIN silver_cadastro_item i ON i.id = ri.item_id
            GROUP BY 1
        ),
        com_ocorrencia AS (
            SELECT DISTINCT agendamento_id FROM silver_fwm_agendamento_ocorrencia
        )
        SELECT {_sk('a.dt_prevista_chegada')}        AS sk_data_prevista,
               {_sk('a.dt_chegada')}                 AS sk_data_chegada,
               a.organizacao_id                     AS sk_cliente,
               a.galpao_id                          AS sk_galpao,
               f.sk_fornecedor                      AS sk_fornecedor,
               v.sk_veiculo                         AS sk_veiculo,
               a.id                                 AS agendamento,
               a.peso_geral, a.peso_cubado, a.qtde_volumes, a.m3,
               CASE WHEN a.dt_chegada > a.dt_prevista_chegada
                    THEN date_diff('minute', a.dt_prevista_chegada, a.dt_chegada)
                    ELSE 0 END                      AS minutos_atraso,
               (a.dt_chegada IS NOT NULL)           AS fl_chegou,
               (a.status = 'NO_SHOW')               AS fl_no_show,
               (a.dt_cancelamento IS NOT NULL)      AS fl_cancelado,
               (oc.agendamento_id IS NOT NULL)      AS fl_com_ocorrencia,
               a.fl_agendamento_web,
               coalesce(vl.valor_recebido, 0)       AS valor_recebido,
               extract(year FROM a.dt_cadastro)::int AS ano
        FROM silver_fwm_agendamento a
        LEFT JOIN gold_dimensoes_dim_fornecedor f ON f.fornecedor = a.fornecedor
        LEFT JOIN gold_dimensoes_dim_veiculo v    ON v.tipo_veiculo = a.tipo_veiculo
        LEFT JOIN com_ocorrencia oc               ON oc.agendamento_id = a.id
        LEFT JOIN valor vl                        ON vl.agendamento_id = a.id
    """,
    "ft_saida": f"""
        WITH fases AS (
            SELECT pf.ss,
                   min(CASE WHEN f.codigo = 'ME' THEN pf.dt_saida END)   AS fim_manuseio,
                   min(CASE WHEN f.codigo = 'EC' THEN pf.dt_entrada END) AS retirada
            FROM silver_fwm_pedido_fase pf
            JOIN silver_cadastro_fase f ON f.id = pf.fase_id
            GROUP BY 1
        )
        SELECT {_sk('m.dt_movimento')}               AS sk_data_saida,
               p.organizacao_id                     AS sk_cliente,
               m.item_id                            AS sk_item,
               m.galpao_id                          AS sk_galpao,
               p.modalidade_id                      AS sk_modalidade,
               m.ss                                 AS ss,
               -m.quantidade                        AS quantidade,
               date_diff('day', p.dt_solicitacao, fs.fim_manuseio) AS dias_manuseio,
               date_diff('day', fs.fim_manuseio, fs.retirada)      AS dias_retirada,
               m.fl_razao_nao_concilia,
               p.fl_timeline_inconsistente,
               extract(year FROM m.dt_movimento)::int AS ano
        FROM silver_fwm_movimento_estoque m
        JOIN silver_fwm_pedido p ON p.ss = m.ss
        LEFT JOIN fases fs       ON fs.ss = m.ss
        WHERE m.tipo = 'SAIDA'
    """,
    "ft_frete": f"""
        WITH minuta_do_pedido AS (
            SELECT mp.ss, min(m.transportador_id) AS transportador_id,
                   min(m.tipo_veiculo) AS tipo_veiculo
            FROM silver_expedicao_minuta_pedido mp
            JOIN silver_expedicao_minuta m ON m.id = mp.minuta_id
            GROUP BY 1
        ),
        material AS (
            SELECT ss, sum(quantidade) AS quantidade_material FROM silver_fwm_pedido_item GROUP BY 1
        )
        SELECT {_sk('ff.dt_faturamento')}            AS sk_data_faturamento,
               {_sk('ff.competencia')}               AS sk_competencia,
               ff.organizacao_id                    AS sk_cliente,
               en.municipio_id                      AS sk_geografia,
               p.modalidade_id                      AS sk_modalidade,
               md.transportador_id                  AS sk_transportador,
               v.sk_veiculo                         AS sk_veiculo,
               fp.sk_faixa_peso                     AS sk_faixa_peso,
               ff.ss                                AS ss,
               ff.valor_frete, ff.valor_frete_icms,
               ff.valor_frete_icms - ff.valor_frete AS icms,
               ff.peso_faturado,
               p.valor_orcamento                    AS valor_material,
               mt.quantidade_material,
               ff.fl_frete_simbolico, ff.fl_dev_reentrega,
               extract(year FROM ff.competencia)::int AS ano
        FROM silver_faturamento_fatura_frete ff
        JOIN silver_fwm_pedido p              ON p.ss = ff.ss
        LEFT JOIN silver_cadastro_endereco en ON en.id = p.endereco_entrega_id
        LEFT JOIN minuta_do_pedido md         ON md.ss = ff.ss
        LEFT JOIN gold_dimensoes_dim_veiculo v ON v.tipo_veiculo = md.tipo_veiculo
        LEFT JOIN gold_dimensoes_dim_faixa_peso fp
               ON ff.peso_faturado >= fp.peso_min
              AND (fp.peso_max IS NULL OR ff.peso_faturado < fp.peso_max)
        LEFT JOIN material mt                 ON mt.ss = ff.ss
    """,
    "ft_validade": f"""
        WITH foto AS (
            SELECT item_id, sum(qtde_saldo) AS saldo
            FROM silver_fwm_estoque_snapshot
            WHERE data = (SELECT max(data) FROM silver_fwm_estoque_snapshot)
            GROUP BY 1
        )
        SELECT {_sk('l.dt_validade')}                AS sk_data_validade,
               i.organizacao_id                     AS sk_cliente,
               l.item_id                            AS sk_item,
               l.codigo                             AS lote,
               l.dt_validade, l.fl_validade_invalida,
               (l.dt_validade < {DATA_CORRENTE})    AS fl_vencido,
               date_diff('day', {DATA_CORRENTE}, l.dt_validade) AS dias_para_vencer,
               coalesce(f.saldo, 0)                 AS saldo_ultima_foto,
               coalesce(f.saldo, 0) * i.valor_unitario AS valor_em_estoque,
               extract(year FROM coalesce(l.dt_validade, l.dt_validade_original))::int AS ano
        FROM silver_fwm_lote l
        JOIN silver_cadastro_item i ON i.id = l.item_id
        LEFT JOIN foto f ON f.item_id = l.item_id
    """,
    "ft_inventario": f"""
        SELECT {_sk('inv.dt_inicio')}                AS sk_data_inicio,
               inv.galpao_id                        AS sk_galpao,
               inv.id                               AS inventario,
               date_diff('day', inv.dt_inicio, inv.dt_termino) AS dias_duracao,
               inv.status,
               (inv.status = 'CONCLUIDO')           AS fl_realizado,
               extract(year FROM inv.dt_inicio)::int AS ano
        FROM silver_fwm_inventario inv
    """,
}
