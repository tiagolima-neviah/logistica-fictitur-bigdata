"""Etapa 1 do gerador: o mundo cadastral da Fictitur.

Geografia, catálogos (fases EA..CE, SLAs, modalidades, parâmetros financeiros),
organizações (matriz + 36 bases + 203 clientes do catálogo do universo Neviah),
endereços-sede, galpões (regra do caso: matriz com GLP01..GLP04; cada base é o
seu próprio galpão), docas, posições de armazém e agentes (usuários,
representantes, transportadores, parceiros). Determinística (semente fixa) e
idempotente: aborta se já houver organizações.
"""

from __future__ import annotations

import csv
import random
from datetime import date
from importlib.resources import files
from typing import Any

import psycopg

from logistica_fictitur.gerador import SEMENTE

FASES = [
    # codigo, nome, ordem, esporadica, horas_meta, horas_limite
    ("EA", "Em Análise", 1, False, 4, 8),
    ("PC", "Pré-Conferência", 2, False, 8, 16),
    ("DC", "Distribuição de Cotas", 3, True, 8, 24),
    ("PL", "Planejamento", 4, False, 8, 16),
    ("EX", "Expedição", 5, True, 8, 24),
    ("CF", "Coleta Física", 6, False, 8, 16),
    ("ME", "Manuseio", 7, False, 16, 32),
    ("EN", "Emissão de NF", 8, False, 4, 8),
    ("EC", "Entrega ao Cliente", 9, False, 48, 96),
    ("CE", "Coleta Externa", 10, False, 24, 48),
]

MODALIDADES = [
    ("RETIRA", "Retira no galpão"),
    ("RODO_FRAC", "Rodoviário fracionado"),
    ("RODO_LOT", "Rodoviário lotação"),
    ("AEREO", "Aéreo"),
    ("EXCLUSIVO", "Veículo exclusivo"),
    ("REDESPACHO", "Redespacho via parceiro"),
    ("LOCAL", "Entrega local"),
    ("TRANSF_BASE", "Transferência para base"),
    ("DEVOLUCAO", "Devolução"),
]

# Parâmetros de negócio (chave, valor, vigência). A política de aging nasce com o
# novo VP, no 2º semestre de 2024 — parte do arco da história.
PARAMETROS = [
    ("taxa_imposto_faturamento", 0.0673, date(2020, 1, 1)),
    ("fator_cubagem_rodoviario", 300, date(2020, 1, 1)),
    ("fator_cubagem_aereo", 166.7, date(2020, 1, 1)),
    ("custo_m3_galpao", 25.00, date(2020, 1, 1)),  # margem de armazenagem é fina de propósito
    ("custo_esteira_por_linha", 3.20, date(2020, 1, 1)),
    ("aliquota_difal_simplificada", 0.04, date(2020, 1, 1)),
    ("icms_interno", 0.12, date(2020, 1, 1)),
    ("icms_interestadual", 0.07, date(2020, 1, 1)),
    ("aging_3_6m", 0.30, date(2024, 8, 1)),
    ("aging_6_9m", 0.60, date(2024, 8, 1)),
    ("aging_9_12m", 0.90, date(2024, 8, 1)),
    ("aging_12m_mais", 1.80, date(2024, 8, 1)),
]

UFS = [
    ("AC", "Acre", "NORTE"), ("AL", "Alagoas", "NORDESTE"), ("AP", "Amapá", "NORTE"),
    ("AM", "Amazonas", "NORTE"), ("BA", "Bahia", "NORDESTE"), ("CE", "Ceará", "NORDESTE"),
    ("DF", "Distrito Federal", "CENTRO-OESTE"), ("ES", "Espírito Santo", "SUDESTE"),
    ("GO", "Goiás", "CENTRO-OESTE"), ("MA", "Maranhão", "NORDESTE"),
    ("MT", "Mato Grosso", "CENTRO-OESTE"), ("MS", "Mato Grosso do Sul", "CENTRO-OESTE"),
    ("MG", "Minas Gerais", "SUDESTE"), ("PA", "Pará", "NORTE"), ("PB", "Paraíba", "NORDESTE"),
    ("PR", "Paraná", "SUL"), ("PE", "Pernambuco", "NORDESTE"), ("PI", "Piauí", "NORDESTE"),
    ("RJ", "Rio de Janeiro", "SUDESTE"), ("RN", "Rio Grande do Norte", "NORDESTE"),
    ("RS", "Rio Grande do Sul", "SUL"), ("RO", "Rondônia", "NORTE"), ("RR", "Roraima", "NORTE"),
    ("SC", "Santa Catarina", "SUL"), ("SP", "São Paulo", "SUDESTE"),
    ("SE", "Sergipe", "NORDESTE"), ("TO", "Tocantins", "NORTE"),
]

# Regiões COMERCIAIS da Fictitur (recorte de negócio, não geografia do IBGE).
REGIOES = ["SP CAPITAL", "SP INTERIOR", "SUDESTE", "SUL", "NORDESTE", "NORTE-CENTRO-OESTE"]
_REGIAO_POR_GEO = {"SUL": "SUL", "NORDESTE": "NORDESTE", "NORTE": "NORTE-CENTRO-OESTE",
                   "CENTRO-OESTE": "NORTE-CENTRO-OESTE", "SUDESTE": "SUDESTE"}

LOGRADOUROS = ["Av. Industrial", "Rua das Acácias", "Av. Brasil", "Rua do Comércio",
               "Av. das Nações", "Rua Projetada", "Estrada Velha", "Av. dos Autonomistas",
               "Rua Barão do Triunfo", "Av. Presidente Kennedy"]
BAIRROS = ["Centro", "Distrito Industrial", "Vila Nova", "Jardim das Indústrias",
           "Parque Logístico", "Vila Operária", "Chácaras Reunidas", "Jardim América"]

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elaine", "Fábio", "Gisele", "Heitor", "Iara",
         "João", "Karen", "Leandro", "Marina", "Nelson", "Olívia", "Paulo", "Quésia",
         "Rafael", "Sônia", "Tiago", "Úrsula", "Vagner", "Wanda", "Xavier", "Yara", "Zeca"]
SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Ferraz", "Gonçalves",
              "Hernandes", "Ito", "Justino", "Klein", "Lopes", "Macedo", "Nogueira",
              "Okamoto", "Peixoto", "Queiroz", "Rezende", "Siqueira", "Teixeira"]
SUFIXOS_TRANSP = ["Transportes", "Logística", "Cargas", "Express", "Fretes", "Rodoviária"]
RADICAIS_TRANSP = ["Horizonte", "Andorinha", "Pioneira", "Atlântico", "Bandeirante",
                   "Cometa", "Diamante", "Estrela", "Falcão", "Gaivota", "Imperial",
                   "Jaguar", "Litoral", "Montanha", "Nacional", "Oceano", "Planalto",
                   "Rápido", "Serrana", "Tucano", "Veloz", "Continental", "Meridional",
                   "Peninsular", "Fronteira", "Rota Sul"]


def _ler_csv(nome: str) -> list[dict[str, str]]:
    caminho = files("logistica_fictitur.gerador").joinpath("dados", nome)
    with caminho.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _cnpj(rnd: random.Random) -> str:
    return f"{rnd.randrange(10_000_000):08d}0001{rnd.randrange(100):02d}"


def _cep(rnd: random.Random) -> str:
    return f"{rnd.randrange(1000, 99999):05d}{rnd.randrange(1000):03d}"


def _data(v: str) -> date | None:
    return date.fromisoformat(v) if v else None


def _regiao_de(cidade: str, uf: str, geo_por_uf: dict[str, str]) -> str:
    if uf == "SP":
        return "SP CAPITAL" if cidade == "São Paulo" else "SP INTERIOR"
    return _REGIAO_POR_GEO[geo_por_uf[uf]]


class MundoCadastral:
    """Executa a etapa e guarda os mapas de id que as próximas etapas usam."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.rnd = random.Random(SEMENTE)
        self.municipio_id: dict[tuple[str, str], int] = {}
        self.org_id: dict[str, int] = {}

    def ja_populado(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cadastro.organizacao")
            linha = cur.fetchone()
            return bool(linha and int(linha[0]) > 0)

    def executar(self) -> dict[str, int]:
        self._geografia()
        self._catalogos()
        self._organizacoes()
        self._galpoes()
        self._agentes()
        self.conn.commit()
        return self._contagens()

    # -- blocos -----------------------------------------------------------

    def _geografia(self) -> None:
        with self.conn.cursor() as cur:
            for i, nome in enumerate(REGIOES, start=1):
                cur.execute("INSERT INTO cadastro.regiao (id, nome) VALUES (%s, %s)", (i, nome))
            cur.executemany(
                "INSERT INTO cadastro.uf (sigla, nome, regiao_geografica) VALUES (%s, %s, %s)",
                UFS,
            )
            geo = {sigla: reg for sigla, _, reg in UFS}
            regiao_id = {nome: i for i, nome in enumerate(REGIOES, start=1)}
            cidades = {(r["cidade"], r["uf"]) for r in _ler_csv("cidades.csv")}
            for arq in ("organizacoes_matriz_bases.csv", "organizacoes_clientes.csv"):
                for r in _ler_csv(arq):
                    if r.get("cidade_sede"):
                        cidades.add((r["cidade_sede"], r["uf_sede"]))
            cidades |= {("Diadema", "SP"), ("São Caetano do Sul", "SP")}
            for cidade, uf in sorted(cidades):
                cur.execute(
                    "INSERT INTO cadastro.municipio (nome, uf, regiao_id) VALUES (%s, %s, %s)"
                    " RETURNING id",
                    (cidade, uf, regiao_id[_regiao_de(cidade, uf, geo)]),
                )
                self.municipio_id[(cidade, uf)] = int(cur.fetchone()[0])  # type: ignore[index]

    def _catalogos(self) -> None:
        with self.conn.cursor() as cur:
            for codigo, nome, ordem, espo, meta, limite in FASES:
                cur.execute(
                    "INSERT INTO cadastro.fase (codigo, nome, ordem, fl_esporadica)"
                    " VALUES (%s, %s, %s, %s) RETURNING id",
                    (codigo, nome, ordem, espo),
                )
                fase_id = int(cur.fetchone()[0])  # type: ignore[index]
                cur.execute(
                    "INSERT INTO cadastro.sla_fase (fase_id, horas_uteis_meta,"
                    " horas_uteis_limite) VALUES (%s, %s, %s)",
                    (fase_id, meta, limite),
                )
            cur.executemany(
                "INSERT INTO cadastro.modalidade (codigo, descricao) VALUES (%s, %s)",
                MODALIDADES,
            )
            cur.executemany(
                "INSERT INTO financeiro.parametro_financeiro (chave, valor, vigencia_inicio)"
                " VALUES (%s, %s, %s)",
                PARAMETROS,
            )

    def _endereco(
        self, cur: psycopg.Cursor, org_id: int | None, tipo: str, cidade: str, uf: str,
        nome_local: str | None = None, cnpj_local: str | None = None,
    ) -> int:
        cur.execute(
            "INSERT INTO cadastro.endereco (organizacao_id, tipo, cnpj_local, nome_local,"
            " logradouro, numero, complemento, bairro, municipio_id, cep)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                org_id, tipo, cnpj_local, nome_local,
                self.rnd.choice(LOGRADOUROS), str(self.rnd.randrange(10, 5000)),
                self.rnd.choice([None, None, "Galpão", "Bloco B", "Fundos"]),
                self.rnd.choice(BAIRROS), self.municipio_id[(cidade, uf)], _cep(self.rnd),
            ),
        )
        return int(cur.fetchone()[0])  # type: ignore[index]

    def _org(self, cur: psycopg.Cursor, r: dict[str, Any]) -> int:
        cur.execute(
            "INSERT INTO cadastro.organizacao (sigla, razao_social, nome_fantasia, cnpj,"
            " tipo_parceria, porte, segmento, fl_entrega_agendada, otif_contratual,"
            " dt_inicio_contrato, dt_cancelamento, ativo)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                r["sigla"], r["razao_social"], r["nome_fantasia"], r["cnpj"],
                r["tipo_parceria"], r.get("porte") or None, r.get("segmento") or None,
                {"True": True, "False": False}.get(str(r.get("fl_entrega_agendada"))),
                r.get("otif_contratual") or None,
                _data(str(r["dt_inicio_contrato"])), _data(str(r.get("dt_cancelamento") or "")),
                str(r.get("ativo", "True")) == "True",
            ),
        )
        org_id = int(cur.fetchone()[0])  # type: ignore[index]
        self.org_id[str(r["sigla"])] = org_id
        return org_id

    def _organizacoes(self) -> None:
        with self.conn.cursor() as cur:
            matriz = {
                "sigla": "FIC", "razao_social": "Fictitur Logística LTDA",
                "nome_fantasia": "Fictitur Logística", "cnpj": _cnpj(self.rnd),
                "tipo_parceria": "MATRIZ", "segmento": "LOGISTICA",
                "dt_inicio_contrato": "2014-03-10", "ativo": "True",
            }
            mid = self._org(cur, matriz)
            self._endereco(cur, mid, "SEDE", "São Paulo", "SP", "Matriz Fictitur")
            for r in _ler_csv("organizacoes_matriz_bases.csv"):
                if r["tipo_parceria"] != "BASE":
                    continue  # a matriz do outro universo não entra: a Fictitur tem a sua
                bid = self._org(cur, r)
                self._endereco(cur, bid, "SEDE", r["cidade_sede"], r["uf_sede"],
                               r["nome_fantasia"], r["cnpj"])
            for r in _ler_csv("organizacoes_clientes.csv"):
                cid = self._org(cur, r)
                cidade, uf = self._cidade_cliente()
                self._endereco(cur, cid, "SEDE", cidade, uf, r["nome_fantasia"], r["cnpj"])

    def _cidade_cliente(self) -> tuple[str, str]:
        linhas = _ler_csv("cidades.csv")
        pesos = [int(r["peso"]) for r in linhas]
        r = self.rnd.choices(linhas, weights=pesos, k=1)[0]
        return r["cidade"], r["uf"]

    def _galpoes(self) -> None:
        # Regra do caso: matriz com GLP01..GLP04 (01/02 no complexo da matriz em São
        # Paulo; 03 em Diadema; 04 em São Caetano do Sul); cada base é o seu galpão.
        matriz = self.org_id["FIC"]
        locais = [("GLP01", "Galpão 1 - Complexo Matriz", "São Paulo", "SP"),
                  ("GLP02", "Galpão 2 - Complexo Matriz", "São Paulo", "SP"),
                  ("GLP03", "Galpão 3 - Diadema", "Diadema", "SP"),
                  ("GLP04", "Galpão 4 - São Caetano", "São Caetano do Sul", "SP")]
        with self.conn.cursor() as cur:
            for codigo, desc, cidade, uf in locais:
                self._galpao(cur, matriz, codigo, desc, cidade, uf, docas=6, grade=(20, 10, 4))
            cur.execute(
                "SELECT o.sigla, m.nome, m.uf FROM cadastro.organizacao o"
                " JOIN cadastro.endereco e ON e.organizacao_id = o.id AND e.tipo = 'SEDE'"
                " JOIN cadastro.municipio m ON m.id = e.municipio_id"
                " WHERE o.tipo_parceria = 'BASE' ORDER BY o.sigla"
            )
            for sigla, cidade, uf in cur.fetchall():
                self._galpao(cur, self.org_id[sigla], f"G-{sigla}", f"Depósito base {sigla}",
                             cidade, uf, docas=2, grade=(5, 4, 2))

    def _galpao(
        self, cur: psycopg.Cursor, org_id: int, codigo: str, desc: str, cidade: str, uf: str,
        docas: int, grade: tuple[int, int, int],
    ) -> None:
        end_id = self._endereco(cur, org_id, "GALPAO", cidade, uf, desc)
        cur.execute(
            "INSERT INTO cadastro.galpao (organizacao_id, codigo, descricao, endereco_id)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (org_id, codigo, desc, end_id),
        )
        galpao_id = int(cur.fetchone()[0])  # type: ignore[index]
        cur.executemany(
            "INSERT INTO cadastro.doca (galpao_id, codigo, descricao) VALUES (%s, %s, %s)",
            [(galpao_id, f"D{i:02d}", f"Doca {i:02d}") for i in range(1, docas + 1)],
        )
        prat, col, alt = grade
        posicoes = [
            (galpao_id, chr(64 + p), str(c), str(a), f"{codigo}-{chr(64 + p)}{c:02d}-{a}",
             round(self.rnd.uniform(1.2, 3.0), 3))
            for p in range(1, prat + 1) for c in range(1, col + 1) for a in range(1, alt + 1)
        ]
        cur.executemany(
            "INSERT INTO cadastro.posicao_armazem (galpao_id, prateleira, coluna, altura,"
            " codigo, m3_posicao) VALUES (%s, %s, %s, %s, %s, %s)",
            posicoes,
        )

    def _agentes(self) -> None:
        rnd = self.rnd
        pessoas = [f"{n} {s}" for n in NOMES for s in SOBRENOMES]
        rnd.shuffle(pessoas)
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO cadastro.usuario (login, nome, departamento) VALUES (%s, %s, %s)",
                [
                    (nome.lower().replace(" ", "."), nome,
                     rnd.choice(["OPERACAO", "EXPEDICAO", "ATENDIMENTO", "PLANEJAMENTO"]))
                    for nome in pessoas[:40]
                ],
            )
            cur.executemany(
                "INSERT INTO cadastro.representante (nome) VALUES (%s)",
                [(nome,) for nome in pessoas[40:210]],
            )
            transportadores = sorted(
                {f"{r} {s}" for r in RADICAIS_TRANSP for s in SUFIXOS_TRANSP}
            )
            rnd.shuffle(transportadores)
            cur.executemany(
                "INSERT INTO cadastro.transportador (razao_social, cnpj) VALUES (%s, %s)",
                [(t, _cnpj(rnd)) for t in transportadores[:130]],
            )
            cur.executemany(
                "INSERT INTO cadastro.parceiro_redespacho (nome) VALUES (%s)",
                [(f"Redespacho {n}",) for n in
                 ["Norte", "Nordeste", "Sul", "Oeste", "Fluvial", "Serrano", "Litorâneo",
                  "Interiorano"]],
            )

    def _contagens(self) -> dict[str, int]:
        saida: dict[str, int] = {}
        with self.conn.cursor() as cur:
            for tabela in ("regiao", "uf", "municipio", "organizacao", "endereco", "galpao",
                           "doca", "posicao_armazem", "fase", "sla_fase", "modalidade",
                           "usuario", "representante", "transportador", "parceiro_redespacho"):
                cur.execute(f"SELECT count(*) FROM cadastro.{tabela}")  # noqa: S608
                saida[tabela] = int(cur.fetchone()[0])  # type: ignore[index]
            cur.execute("SELECT count(*) FROM financeiro.parametro_financeiro")
            saida["parametro_financeiro"] = int(cur.fetchone()[0])  # type: ignore[index]
        return saida
