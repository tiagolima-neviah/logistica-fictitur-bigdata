-- Schema cadastro: entidades mestres e parametrização (20 tabelas).

CREATE TABLE cadastro.regiao (
    id          smallint PRIMARY KEY,
    nome        varchar(40) NOT NULL UNIQUE
);

CREATE TABLE cadastro.uf (
    sigla               char(2) PRIMARY KEY,
    nome                varchar(40) NOT NULL,
    regiao_geografica   varchar(20) NOT NULL
);

CREATE TABLE cadastro.municipio (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome        varchar(80) NOT NULL,
    uf          char(2) NOT NULL REFERENCES cadastro.uf (sigla),
    regiao_id   smallint REFERENCES cadastro.regiao (id),
    UNIQUE (nome, uf)
);

CREATE TABLE cadastro.organizacao (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sigla               varchar(10) NOT NULL UNIQUE,
    razao_social        varchar(150) NOT NULL,
    nome_fantasia       varchar(150) NOT NULL,
    cnpj                char(14) NOT NULL UNIQUE,
    tipo_parceria       varchar(10) NOT NULL CHECK (tipo_parceria IN ('CLIENTE', 'BASE', 'MATRIZ')),
    porte               varchar(10) CHECK (porte IS NULL OR porte IN ('MICRO', 'PEQUENA', 'MEDIA', 'GRANDE', 'MEGA')),
    segmento            varchar(40),
    fl_entrega_agendada boolean,
    otif_contratual     numeric(4, 2),
    dt_inicio_contrato  date NOT NULL,
    dt_cancelamento     date,
    ativo               boolean NOT NULL DEFAULT true
);

CREATE TABLE cadastro.endereco (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id  bigint REFERENCES cadastro.organizacao (id),
    tipo            varchar(10) NOT NULL CHECK (tipo IN ('SEDE', 'ENTREGA', 'GALPAO', 'COLETA')),
    cnpj_local      char(14),
    nome_local      varchar(150),
    logradouro      varchar(120) NOT NULL,
    numero          varchar(10),
    complemento     varchar(60),
    bairro          varchar(80),
    municipio_id    bigint NOT NULL REFERENCES cadastro.municipio (id),
    cep             char(8),
    ativo           boolean NOT NULL DEFAULT true
);

-- Galpão = local físico de armazenagem. Pertence a uma organização (MATRIZ ou BASE);
-- uma organização pode ter 0..N galpões, cada um com endereço PRÓPRIO (1:1).
-- Regra deste CASE: só a MATRIZ tem múltiplos galpões (GLP01..GLP04, endereços que
-- podem diferir entre si); cada BASE é ela própria o seu único galpão, no endereço dela.
CREATE TABLE cadastro.galpao (
    id              smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id  bigint NOT NULL REFERENCES cadastro.organizacao (id),
    codigo          varchar(10) NOT NULL UNIQUE,   -- GLP01..GLP04 (matriz), depósitos das bases
    descricao       varchar(60) NOT NULL,
    endereco_id     bigint NOT NULL UNIQUE REFERENCES cadastro.endereco (id)
);

CREATE TABLE cadastro.doca (
    id          smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    galpao_id   smallint NOT NULL REFERENCES cadastro.galpao (id),
    codigo      varchar(10) NOT NULL,
    descricao   varchar(60),
    ativo       boolean NOT NULL DEFAULT true,
    UNIQUE (galpao_id, codigo)
);

CREATE TABLE cadastro.posicao_armazem (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    galpao_id   smallint NOT NULL REFERENCES cadastro.galpao (id),
    prateleira  varchar(10) NOT NULL,
    coluna      varchar(10) NOT NULL,
    altura      varchar(10) NOT NULL,
    codigo      varchar(30) NOT NULL,          -- endereçamento completo legível
    m3_posicao  numeric(8, 3) NOT NULL,
    UNIQUE (galpao_id, codigo)
);

CREATE TABLE cadastro.transportador (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    razao_social    varchar(150) NOT NULL,
    cnpj            char(14) UNIQUE,
    ativo           boolean NOT NULL DEFAULT true
);

CREATE TABLE cadastro.parceiro_redespacho (
    id      smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome    varchar(80) NOT NULL UNIQUE
);

CREATE TABLE cadastro.usuario (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login           varchar(60) NOT NULL UNIQUE,
    nome            varchar(120) NOT NULL,
    departamento    varchar(40),
    ativo           boolean NOT NULL DEFAULT true
);

CREATE TABLE cadastro.representante (
    id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome    varchar(120) NOT NULL,
    ativo   boolean NOT NULL DEFAULT true
);

CREATE TABLE cadastro.modalidade (
    id          smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo      varchar(20) NOT NULL UNIQUE,   -- RETIRA, RODOVIARIO, AEREO, EXCLUSIVO...
    descricao   varchar(60) NOT NULL
);

CREATE TABLE cadastro.item (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id      bigint NOT NULL REFERENCES cadastro.organizacao (id),
    cod_item            varchar(30) NOT NULL,  -- código interno Fictitur
    cod_item_cliente    varchar(30),
    descricao           varchar(200) NOT NULL,
    grupo               varchar(60),
    subgrupo            varchar(60),
    marca               varchar(60),
    estrategia          varchar(40),
    categoria           varchar(60),
    material            varchar(60),
    classe_anvisa       varchar(20),
    altura_cm           numeric(8, 2),
    largura_cm          numeric(8, 2),
    comprimento_cm      numeric(8, 2),
    peso_kg             numeric(10, 3),
    multiplo_saida      integer,
    qtd_amarracao       integer,
    pcs_pallet          integer,
    valor_unitario      numeric(12, 2),
    url_foto            text,
    ativo               boolean NOT NULL DEFAULT true,
    UNIQUE (organizacao_id, cod_item)
);

CREATE TABLE cadastro.cota (
    id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES cadastro.item (id),
    nivel1  varchar(60),
    nivel2  varchar(60),
    nivel3  varchar(60),
    nivel4  varchar(60)
);

CREATE TABLE cadastro.sla_manuseio (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organizacao_id          bigint NOT NULL UNIQUE REFERENCES cadastro.organizacao (id),
    hora_corte              time NOT NULL DEFAULT '12:00',
    dias_pre_corte          smallint NOT NULL,
    dias_pos_corte          smallint NOT NULL,
    dias_pre_corte_retira   smallint NOT NULL,
    dias_pos_corte_retira   smallint NOT NULL
);

CREATE TABLE cadastro.sla_transporte (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uf              char(2) NOT NULL REFERENCES cadastro.uf (sigla),
    municipio_id    bigint REFERENCES cadastro.municipio (id),
    modalidade_id   smallint NOT NULL REFERENCES cadastro.modalidade (id),
    dias_prazo      smallint NOT NULL,
    UNIQUE (uf, municipio_id, modalidade_id)
);

CREATE TABLE cadastro.meta_frete (
    id              smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    regiao_id       smallint NOT NULL REFERENCES cadastro.regiao (id),
    tipo_destino    varchar(15) NOT NULL CHECK (tipo_destino IN ('LOJA', 'BASE', 'DISTRIBUIDOR', 'REPS')),
    target_rs_kg    numeric(8, 3) NOT NULL,
    UNIQUE (regiao_id, tipo_destino)
);

-- As 10 fases do ciclo de vida do pedido (padrão do universo Neviah):
-- EA Em Análise · PC Pré-Conferência · DC Distribuição de Cotas · PL Planejamento ·
-- EX Expedição · CF Coleta Física · ME Manuseio · EN Emissão de NF ·
-- EC Entrega ao Cliente · CE Coleta Externa. DC e EX são esporádicas.
CREATE TABLE cadastro.fase (
    id              smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          char(2) NOT NULL UNIQUE,
    nome            varchar(60) NOT NULL,
    ordem           smallint NOT NULL UNIQUE,
    fl_esporadica   boolean NOT NULL DEFAULT false
);

-- Régua INTERNA de duração de cada fase, em horas úteis. Dias NÃO se armazena:
-- deriva (horas / 8) na exibição, "derivado se calcula".
CREATE TABLE cadastro.sla_fase (
    id                  smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fase_id             smallint NOT NULL UNIQUE REFERENCES cadastro.fase (id),
    horas_uteis_meta    integer NOT NULL,
    horas_uteis_limite  integer NOT NULL
);
