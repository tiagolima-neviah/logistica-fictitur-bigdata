-- Schema faturamento: receitas (3 tabelas). Competência = 1º dia do mês faturado.

CREATE TABLE faturamento.fatura_frete (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id      bigint NOT NULL REFERENCES cadastro.organizacao (id),
    ss                  bigint REFERENCES fwm.pedido (ss),
    os_id               bigint REFERENCES fwm.os (id),
    modal               varchar(20),
    tipo_destino        varchar(15),               -- LOJA, BASE, DISTRIBUIDOR, REPS
    valor_frete         numeric(14, 2) NOT NULL,   -- sem ICMS
    valor_frete_icms    numeric(14, 2) NOT NULL,   -- com ICMS (o faturado)
    peso_faturado       numeric(12, 3),
    fl_dev_reentrega    boolean NOT NULL DEFAULT false,
    dt_faturamento      date NOT NULL,
    dt_liberacao        date,
    competencia         date NOT NULL
);
CREATE INDEX ix_fatura_frete_comp ON faturamento.fatura_frete (competencia, organizacao_id);

CREATE TABLE faturamento.fatura_armazenagem (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id          bigint NOT NULL REFERENCES cadastro.organizacao (id),
    competencia             date NOT NULL,
    m3_medio                numeric(12, 3) NOT NULL,
    valor_material_medio    numeric(16, 2) NOT NULL,
    valor_cobrado           numeric(14, 2) NOT NULL,
    dt_faturamento          date NOT NULL,
    UNIQUE (organizacao_id, competencia)
);

CREATE TABLE faturamento.fatura_servico (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    tipo            varchar(25) NOT NULL
        CHECK (tipo IN ('COLETA', 'POSITIVACAO', 'SERVICO_COMPLEMENTAR')),
    coleta_id       bigint REFERENCES expedicao.coleta (id),
    positivacao_id  bigint REFERENCES fwm.positivacao (id),
    scc_id          bigint REFERENCES fwm.servico_complementar (id),
    valor           numeric(14, 2) NOT NULL,
    dt_faturamento  date NOT NULL,
    competencia     date NOT NULL
);
