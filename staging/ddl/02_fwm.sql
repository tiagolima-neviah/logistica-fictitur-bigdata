-- Schema fwm (Fictitur Warehouse Management): operação de pedidos, recebimento, estoque e serviços (17 tabelas).
-- Denormalizações PROPOSITAIS (sujeira estrutural que a silver conforma): descrição
-- de item gravada no momento em pedido_item/recebimento_item; cidade/uf/cep
-- fotografados no pedido além do endereço referenciado.
-- Fases do pedido: catálogo em cadastro.fase (EA..CE); histórico em fwm.pedido_fase.

CREATE TABLE fwm.pedido (
    ss                  bigint PRIMARY KEY,
    organizacao_id      bigint NOT NULL REFERENCES cadastro.organizacao (id),
    solicitante_id      bigint REFERENCES cadastro.usuario (id),
    usuario_id          bigint REFERENCES cadastro.usuario (id),
    origem              varchar(10) NOT NULL CHECK (origem IN ('API', 'GRADE', 'WEB', 'OUTROS')),
    endereco_entrega_id bigint REFERENCES cadastro.endereco (id),
    destinatario        varchar(150),
    aos_cuidados        varchar(120),
    cidade              varchar(80),           -- fotografia do momento (denormalização proposital)
    uf                  char(2),
    cep                 char(8),
    modalidade_id       smallint REFERENCES cadastro.modalidade (id),
    representante_id    bigint REFERENCES cadastro.representante (id),
    campanha            varchar(80),
    tipo_destino        varchar(15),
    fl_impreterivel     boolean NOT NULL DEFAULT false,
    fl_base             boolean NOT NULL DEFAULT false,
    fl_entrega_agendada boolean NOT NULL DEFAULT false,
    nf_cliente          varchar(20),
    valor_orcamento     numeric(14, 2),
    dt_solicitacao      timestamp NOT NULL,
    fase_id             smallint NOT NULL REFERENCES cadastro.fase (id),   -- fase ATUAL
    qtde_ocam           integer,               -- ordens de manuseio geradas na fase ME
    departamento        varchar(40)
);
CREATE INDEX ix_pedido_org_dt ON fwm.pedido (organizacao_id, dt_solicitacao);

CREATE TABLE fwm.pedido_item (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ss              bigint NOT NULL REFERENCES fwm.pedido (ss),
    item_id         bigint NOT NULL REFERENCES cadastro.item (id),
    descricao_item  varchar(200),              -- texto do momento (denormalização proposital)
    quantidade      integer NOT NULL,
    valor_unitario  numeric(12, 2),
    valor_total     numeric(14, 2)
);
CREATE INDEX ix_pedido_item_ss ON fwm.pedido_item (ss);

-- Histórico LONGO das fases (padrão TFB): cada passagem é um evento entrada/saída;
-- dt_saida NULL = fase atual. Durações NUNCA são colunas: derivam dos timestamps.
CREATE TABLE fwm.pedido_fase (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ss          bigint NOT NULL REFERENCES fwm.pedido (ss),
    fase_id     smallint NOT NULL REFERENCES cadastro.fase (id),
    dt_entrada  timestamp NOT NULL,
    dt_saida    timestamp,
    usuario_id  bigint REFERENCES cadastro.usuario (id),
    UNIQUE (ss, fase_id)
);
CREATE INDEX ix_pedido_fase_ss ON fwm.pedido_fase (ss);

CREATE TABLE fwm.os (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nr_os       integer NOT NULL,
    ano_os      smallint NOT NULL,
    ss          bigint REFERENCES fwm.pedido (ss),
    dt_abertura timestamp,
    UNIQUE (nr_os, ano_os)
);

CREATE TABLE fwm.nf (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero      bigint NOT NULL,
    ss          bigint REFERENCES fwm.pedido (ss),
    dt_emissao  timestamp NOT NULL,
    valor       numeric(14, 2)
);
CREATE INDEX ix_nf_ss ON fwm.nf (ss);

CREATE TABLE fwm.agendamento (
    id                  bigint PRIMARY KEY,    -- numeroAgendamento
    organizacao_id      bigint NOT NULL REFERENCES cadastro.organizacao (id),
    galpao_id           smallint REFERENCES cadastro.galpao (id),
    doca_id             smallint REFERENCES cadastro.doca (id),
    fornecedor          varchar(150),
    sub_fornecedor      varchar(150),
    transportadora      varchar(150),
    tipo_veiculo        varchar(40),
    tipo_or_id          smallint,
    tipo_or             varchar(40),
    dt_cadastro         timestamp NOT NULL,
    dt_prevista_chegada timestamp,
    dt_chegada          timestamp,
    dt_cancelamento     timestamp,
    login_cancelamento  varchar(60),
    motivo_cancelamento varchar(200),
    peso_geral          numeric(12, 3),
    peso_cubado         numeric(12, 3),
    qtde_volumes        integer,
    m3                  numeric(12, 3),
    tipo_carga          varchar(30),
    capacidade          varchar(30),
    nfs                 text,
    nr_coleta           bigint,
    batida              varchar(30),
    eo                  varchar(30),
    origem_cli          varchar(60),
    fl_agendamento_web  boolean NOT NULL DEFAULT false,
    status_id           smallint,
    status              varchar(60)
);
CREATE INDEX ix_agendamento_org_dt ON fwm.agendamento (organizacao_id, dt_chegada);

CREATE TABLE fwm.agendamento_ocorrencia (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agendamento_id  bigint NOT NULL REFERENCES fwm.agendamento (id),
    dt              timestamp NOT NULL,
    descricao       varchar(200) NOT NULL
);

CREATE TABLE fwm.ordem_recebimento (
    id                  bigint PRIMARY KEY,    -- IdOR
    agendamento_id      bigint NOT NULL REFERENCES fwm.agendamento (id),
    dt_or               timestamp,
    cod_receb           varchar(30),
    status_id           smallint,
    status              varchar(60),
    dt_liberacao_doca   timestamp,
    dt_prevista_fim     timestamp
);

CREATE TABLE fwm.recebimento_item (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ordem_recebimento_id    bigint NOT NULL REFERENCES fwm.ordem_recebimento (id),
    item_id                 bigint NOT NULL REFERENCES cadastro.item (id),
    descricao_item          varchar(200),      -- texto do momento (denormalização proposital)
    quantidade              integer NOT NULL,
    sla_recebimento         varchar(30),
    sla_cota                varchar(30),
    dt_transporte           date,
    dt_recebimento          date,
    dt_subida_cota          date,
    galpao_destino_id       smallint REFERENCES cadastro.galpao (id)   -- galpão (matriz ou base) que recebeu
);
CREATE INDEX ix_receb_item_or ON fwm.recebimento_item (ordem_recebimento_id);

CREATE TABLE fwm.lote (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                     bigint NOT NULL REFERENCES cadastro.item (id),
    codigo                      varchar(40) NOT NULL,
    dt_validade                 date,
    dt_validade_alternativa     date,
    dt_validade_calculada       date,
    vencimento_dias_revalidacao integer,
    UNIQUE (item_id, codigo)
);

CREATE TABLE fwm.movimento_estoque (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                 bigint NOT NULL REFERENCES cadastro.item (id),
    lote_id                 bigint REFERENCES fwm.lote (id),
    posicao_id              bigint REFERENCES cadastro.posicao_armazem (id),
    galpao_id               smallint NOT NULL REFERENCES cadastro.galpao (id),  -- local físico (matriz ou base)
    tipo                    varchar(15) NOT NULL
        CHECK (tipo IN ('ENTRADA', 'SAIDA', 'AJUSTE', 'TRANSFERENCIA', 'INVENTARIO')),
    quantidade              integer NOT NULL,  -- positivo entra, negativo sai
    dt_movimento            timestamp NOT NULL,
    ss                      bigint REFERENCES fwm.pedido (ss),
    ordem_recebimento_id    bigint REFERENCES fwm.ordem_recebimento (id),
    inventario_id           bigint
);
CREATE INDEX ix_mov_estoque_item_dt ON fwm.movimento_estoque (item_id, dt_movimento);
CREATE INDEX ix_mov_estoque_dt ON fwm.movimento_estoque (dt_movimento);

CREATE TABLE fwm.estoque_saldo (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id             bigint NOT NULL REFERENCES cadastro.item (id),
    lote_id             bigint REFERENCES fwm.lote (id),
    posicao_id          bigint REFERENCES cadastro.posicao_armazem (id),
    galpao_id           smallint NOT NULL REFERENCES cadastro.galpao (id),
    saldo               integer NOT NULL,
    reservado           integer NOT NULL DEFAULT 0,
    em_cota             integer NOT NULL DEFAULT 0,
    dt_atualizacao      timestamp NOT NULL
);
CREATE UNIQUE INDEX ux_estoque_saldo_chave
    ON fwm.estoque_saldo (item_id, COALESCE(lote_id, 0), COALESCE(posicao_id, 0), galpao_id);

-- Foto oficial do estoque gerada pelo PRÓPRIO sistema (padrão TFB estoque_snapshot):
-- fechamento mensal + diária no mês corrente. É a base da cobrança de armazenagem;
-- não confundir com acúmulo de fotos de BI (removido do modelo por decisão do Tiago).
CREATE TABLE fwm.estoque_snapshot (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data                date NOT NULL,
    item_id             bigint NOT NULL REFERENCES cadastro.item (id),
    galpao_id           smallint NOT NULL REFERENCES cadastro.galpao (id),
    qtde_saldo          integer NOT NULL,
    m3_ocupado          numeric(12, 4) NOT NULL,
    valor_material      numeric(14, 2) NOT NULL,   -- congelado na foto
    valor_danificado    numeric(14, 2) NOT NULL DEFAULT 0,
    dias_sem_movimento  integer,
    UNIQUE (data, item_id, galpao_id)
);

CREATE TABLE fwm.inventario (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    galpao_id           smallint NOT NULL REFERENCES cadastro.galpao (id),
    dt_criado           timestamp NOT NULL,
    dt_inicio           timestamp,
    dt_termino          timestamp,
    status              varchar(30)
);

CREATE TABLE fwm.inventario_item (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    inventario_id   bigint NOT NULL REFERENCES fwm.inventario (id),
    item_id         bigint NOT NULL REFERENCES cadastro.item (id),
    lote_id         bigint REFERENCES fwm.lote (id),
    qtde_sistema    integer NOT NULL,
    qtde_contada    integer
);

CREATE TABLE fwm.servico_complementar (
    id              bigint PRIMARY KEY,        -- número da SCC
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    os_id           bigint REFERENCES fwm.os (id),
    tipo            varchar(40) NOT NULL,      -- Grade, Montagem de Kit...
    servico         varchar(60),
    tcs_orcamento   bigint,
    tcs_execucao    bigint,
    custo_insumo    numeric(12, 2) NOT NULL DEFAULT 0,
    custo_mao_obra  numeric(12, 2) NOT NULL DEFAULT 0,
    solicitante_id  bigint REFERENCES cadastro.usuario (id),
    dt_scc          date NOT NULL,
    dt_os           date
);

CREATE TABLE fwm.positivacao (
    id              bigint PRIMARY KEY,        -- Nº da positivação
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    os_id           bigint REFERENCES fwm.os (id),
    campanha        varchar(80),
    loja_nome       varchar(150),
    loja_endereco   varchar(200),
    ss_referencia   bigint REFERENCES fwm.pedido (ss),
    dt_abertura     timestamp NOT NULL,
    dt_servico      date,
    custo           numeric(12, 2),
    valor_cobrado   numeric(12, 2),
    status          varchar(30)
);
