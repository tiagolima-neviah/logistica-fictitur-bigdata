-- Schema expedicao: transporte, entregas, ocorrências e coletas (6 tabelas).

CREATE TABLE expedicao.minuta (
    id                      bigint PRIMARY KEY,    -- número da minuta
    dt_criacao              timestamp NOT NULL,
    dt_expedicao            timestamp,
    transportador_id        bigint REFERENCES cadastro.transportador (id),
    parceiro_redespacho_id  smallint REFERENCES cadastro.parceiro_redespacho (id),
    tipo_veiculo            varchar(40),           -- FIORINO, VUC, TRUCK, CARRETA...
    placa                   varchar(10),
    rota                    varchar(80),
    tipo_carga              varchar(15) CHECK (tipo_carga IN ('CONSOLIDADA', 'EXCLUSIVA'))
);

CREATE TABLE expedicao.minuta_pedido (
    minuta_id   bigint NOT NULL REFERENCES expedicao.minuta (id),
    ss          bigint NOT NULL REFERENCES fwm.pedido (ss),
    PRIMARY KEY (minuta_id, ss)
);

CREATE TABLE expedicao.motivo_atraso (
    id          smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descricao   varchar(120) NOT NULL UNIQUE
);

CREATE TABLE expedicao.entrega (
    ss                      bigint PRIMARY KEY REFERENCES fwm.pedido (ss),
    prazo_inicial_cliente   date,
    prazo_interno           date,                  -- prazo Fictitur
    dt_real_prevista        date,
    dt_agendamento          date,
    dt_entrega              timestamp,
    recebedor               varchar(120),
    fl_canhoto              boolean NOT NULL DEFAULT false,
    motivo_atraso_id        smallint REFERENCES expedicao.motivo_atraso (id)
);

CREATE TABLE expedicao.ocorrencia_entrega (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ss                  bigint NOT NULL REFERENCES fwm.pedido (ss),
    dt                  timestamp NOT NULL,
    tipo                varchar(15) NOT NULL
        CHECK (tipo IN ('OCORRENCIA', 'DEVOLUCAO', 'REENTREGA', 'AVARIA', 'EVENTO')),
    descricao           varchar(200),
    motivo_atraso_id    smallint REFERENCES expedicao.motivo_atraso (id)
);
CREATE INDEX ix_ocorrencia_ss ON expedicao.ocorrencia_entrega (ss);

CREATE TABLE expedicao.coleta (
    id                  bigint PRIMARY KEY,        -- nº da coleta
    organizacao_id      bigint NOT NULL REFERENCES cadastro.organizacao (id),
    os_id               bigint REFERENCES fwm.os (id),
    tipo_veiculo        varchar(40),
    motorista           varchar(120),
    fl_cancelada        boolean NOT NULL DEFAULT false,
    dt_abertura         timestamp NOT NULL,
    dt_real             timestamp,
    solicitante         varchar(120),
    observacao          text,
    cnpj_origem         char(14),
    nome_origem         varchar(150),
    endereco_origem     varchar(200),
    municipio_origem    varchar(80),
    uf_origem           char(2),
    cnpj_destino        char(14),
    nome_destino        varchar(150),
    endereco_destino    varchar(200),
    municipio_destino   varchar(80),
    uf_destino          char(2),
    volume              integer,
    peso                numeric(12, 3),
    nf                  varchar(20),
    dt_nf               date,
    valor_nf            numeric(14, 2),
    modalidade_id       smallint REFERENCES cadastro.modalidade (id)
);
