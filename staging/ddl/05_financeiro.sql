-- Schema financeiro: custos, tarifas e parâmetros (4 tabelas). Motor do BI de margens.
-- Regras: cofre TFB (regras_derivadas_mc) aplicado ao case Fictitur.

CREATE TABLE financeiro.parametro_financeiro (
    chave           varchar(40) NOT NULL,      -- taxa_imposto_faturamento, fator_cubagem_rodoviario,
    valor           numeric(12, 4) NOT NULL,   -- fator_cubagem_aereo, custo_m3_galpao, custo_esteira_por_linha,
    vigencia_inicio date NOT NULL,             -- icms_interno, icms_interestadual, aliquota_difal_simplificada,
    descricao       varchar(200),              -- aging_3_6m, aging_6_9m, aging_9_12m, aging_12m_mais
    PRIMARY KEY (chave, vigencia_inicio)
);

CREATE TABLE financeiro.tarifa_armazenagem (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id          bigint NOT NULL REFERENCES cadastro.organizacao (id),
    valor_m3                numeric(10, 2) NOT NULL,
    aliquota_ad_valorem     numeric(7, 5) NOT NULL,
    valor_minimo_mensal     numeric(12, 2) NOT NULL DEFAULT 0,
    vigencia_inicio         date NOT NULL,
    UNIQUE (organizacao_id, vigencia_inicio)
);

CREATE TABLE financeiro.tarifa_frete (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    modalidade_id   smallint NOT NULL REFERENCES cadastro.modalidade (id),
    uf              char(2) NOT NULL REFERENCES cadastro.uf (sigla),
    faixa_peso_min  numeric(10, 2) NOT NULL DEFAULT 0,
    faixa_peso_max  numeric(10, 2),
    preco_teorico   numeric(12, 2) NOT NULL,   -- o vl_preco_teo da referência
    vigencia_inicio date NOT NULL
);

CREATE TABLE financeiro.custo_operacao (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    categoria       varchar(20) NOT NULL CHECK (categoria IN
        ('CUSTO_FRETE', 'COLETA', 'INSUMOS', 'MAO_DE_OBRA', 'IMPOSTO_DIFAL', 'DEV_REENTREGA')),
    ss              bigint REFERENCES fwm.pedido (ss),
    os_id           bigint REFERENCES fwm.os (id),
    coleta_id       bigint REFERENCES expedicao.coleta (id),
    scc_id          bigint REFERENCES fwm.servico_complementar (id),
    positivacao_id  bigint REFERENCES fwm.positivacao (id),
    valor           numeric(14, 2) NOT NULL,
    competencia     date NOT NULL,
    dt_lancamento   date NOT NULL,
    descricao       varchar(200)
);
CREATE INDEX ix_custo_op_comp ON financeiro.custo_operacao (competencia, organizacao_id, categoria);
