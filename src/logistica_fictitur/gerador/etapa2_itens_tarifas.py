"""Etapa 2 do gerador: catálogo comercial e réguas de prazo.

Itens por cliente (o gabarito dita quantos e com que perfil de preço), cotas,
endereços de entrega (destinatários), tarifas de frete e de armazenagem, SLAs
de manuseio e de transporte e o catálogo de motivos de atraso. Determinística
e idempotente (aborta o bloco se `cadastro.item` já estiver populado).

Sujeira cadastral plantada AQUI (é estática do cadastro): ~1,5% dos itens sem
valor unitário — o furo de cobertura fiscal que a régua exige e a silver acha.
"""

from __future__ import annotations

import random
from typing import Any

import psycopg

from logistica_fictitur.gerador import SEMENTE
from logistica_fictitur.gerador.etapa1_cadastro import _cep, _cnpj, _ler_csv

# vocabulário de produto por segmento (fallback DEFAULT); grupo -> subgrupos
VOCAB: dict[str, list[tuple[str, list[str]]]] = {
    "ALIMENTICIO": [("Chocolates", ["Barras", "Bombons", "Ovos Sazonais"]),
                    ("Biscoitos", ["Recheados", "Salgados"]),
                    ("Bebidas", ["Sucos", "Achocolatados"])],
    "COSMETICOS_DERMATOLOGICOS": [("Dermocosméticos", ["Protetor Solar", "Hidratantes"]),
                                  ("Cabelos", ["Shampoo", "Condicionador"]),
                                  ("Combate a Dor", ["Géis Tópicos"])],
    "ELETRONICOS": [("Áudio", ["Fones", "Caixas de Som"]),
                    ("Acessórios", ["Cabos", "Carregadores", "Capas"]),
                    ("Informática", ["Mouses", "Teclados"])],
    "MODA_ACESSORIOS": [("Bolsas", ["Couro", "Sintética"]),
                        ("Bijuterias", ["Colares", "Brincos"]),
                        ("Óculos", ["Solar", "Armações"])],
    "QUIMICO_LIMPEZA": [("Limpeza Profissional", ["Detergentes", "Desinfetantes"]),
                        ("Linha Doméstica", ["Multiuso", "Amaciantes"])],
    "SAUDE_HUMANA": [("Medicamentos", ["Genéricos", "Referência"]),
                     ("Hospitalar", ["Descartáveis", "Curativos"])],
    "DEFAULT": [("Linha Principal", ["Padrão", "Premium"]),
                ("Acessórios", ["Reposição", "Kits"])],
}
MARCAS_RADICAL = ["Aurora", "Vetta", "Prisma", "Lumen", "Solaris", "Andina", "Nobre",
                  "Vivace", "Terral", "Coral", "Origem", "Alva"]
DESTINATARIO_SUFIXO = ["Distribuidora", "Comércio", "Atacadão", "Mercado", "Farmácia",
                       "Magazine", "Depósito", "Casa"]
DESTINATARIO_RADICAL = ["São Jorge", "Bela Vista", "Primavera", "Central", "União",
                        "Esperança", "Vitória", "Aliança", "Progresso", "Ideal",
                        "Moderna", "Popular", "Econômico", "Estrela", "Continental"]

MOTIVOS_ATRASO = [
    "Veículo quebrado em rota", "Extravio parcial de volumes", "Endereço não localizado",
    "Destinatário ausente", "Recusa no recebimento", "Greve ou paralisação",
    "Interdição de rodovia", "Clima severo na região", "Avaria na carga",
    "Falta de agendamento do destinatário", "Agenda do destinatário lotada",
    "Atraso do transportador parceiro", "Roubo de carga", "Fiscalização em posto fiscal",
    "Erro de emissão de NF", "Divergência de estoque na separação",
    "Capacidade de veículo insuficiente", "Reprogramação a pedido do cliente",
    "Falha em transbordo na base", "Volume retido para conferência",
]

# dias de prazo de transporte por região comercial (base rodoviário fracionado)
DIAS_POR_REGIAO = {"SP CAPITAL": (1, 2), "SP INTERIOR": (2, 3), "SUDESTE": (2, 4),
                   "SUL": (3, 5), "NORDESTE": (5, 9), "NORTE-CENTRO-OESTE": (6, 11)}
# R$/kg de referência por região (base para o preço teórico)
RSKG_POR_REGIAO = {"SP CAPITAL": 0.9, "SP INTERIOR": 1.1, "SUDESTE": 1.4, "SUL": 1.8,
                   "NORDESTE": 2.6, "NORTE-CENTRO-OESTE": 3.2}
FATOR_MODAL = {"RODO_FRAC": 1.0, "RODO_LOT": 0.7, "AEREO": 3.4}

TAXA_ITEM_SEM_VALOR = 0.015


class CatalogoComercial:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.rnd = random.Random(SEMENTE + 2)

    def ja_populado(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM cadastro.item")
            linha = cur.fetchone()
            return bool(linha and int(linha[0]) > 0)

    def executar(self) -> dict[str, int]:
        self._carregar_mundo()
        self._itens_e_cotas()
        self._destinatarios()
        self._slas()
        self._tarifas()
        self._motivos()
        self.conn.commit()
        return self._contagens()

    def _carregar_mundo(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT o.id, o.sigla, o.segmento, o.porte FROM cadastro.organizacao o"
                " WHERE o.tipo_parceria = 'CLIENTE' ORDER BY o.id"
            )
            self.clientes: list[dict[str, Any]] = [
                {"id": int(i), "sigla": str(s), "segmento": str(seg or "DEFAULT"),
                 "porte": str(p)}
                for i, s, seg, p in cur.fetchall()
            ]
            cur.execute("SELECT id, codigo FROM cadastro.modalidade")
            self.modalidade_id = {str(c): int(i) for i, c in cur.fetchall()}
            cur.execute(
                "SELECT m.id, m.nome, m.uf, r.nome FROM cadastro.municipio m"
                " JOIN cadastro.regiao r ON r.id = m.regiao_id"
            )
            self.municipios: list[dict[str, Any]] = [
                {"id": int(i), "nome": str(n), "uf": str(u), "regiao": str(rg)}
                for i, n, u, rg in cur.fetchall()
            ]
            self.regiao_da_uf: dict[str, str] = {}
            for m in self.municipios:  # regiao "default" da UF = a mais comum entre municípios
                self.regiao_da_uf.setdefault(m["uf"], m["regiao"])
            cur.execute("SELECT sigla FROM cadastro.uf")
            self.ufs = [str(u) for (u,) in cur.fetchall()]
        self.gabarito = {r["sigla"]: r for r in _ler_csv("gabarito_clientes.csv")}

    def _itens_e_cotas(self) -> None:
        rnd = self.rnd
        with self.conn.cursor() as cur:
            for cli in self.clientes:
                g = self.gabarito[cli["sigla"]]
                n_itens = int(g["n_itens"])
                fator_preco = float(g["fator_preco"])
                estoca = g["estoca"] == "True"
                vocab = VOCAB.get(cli["segmento"], VOCAB["DEFAULT"])
                marcas = rnd.sample(MARCAS_RADICAL, k=min(4, max(2, n_itens // 30)))
                for i in range(1, n_itens + 1):
                    grupo, subgrupos = vocab[i % len(vocab)]
                    subgrupo = subgrupos[i % len(subgrupos)]
                    marca = marcas[i % len(marcas)]
                    apres = rnd.choice(["120g", "250g", "500ml", "1L", "Un", "Kit 3", "Pack 6"])
                    peso = round(rnd.uniform(0.05, 4.0) ** 2 + 0.05, 3)
                    alt = round(rnd.uniform(4, 60), 1)
                    larg = round(rnd.uniform(4, 60), 1)
                    comp = round(rnd.uniform(6, 80), 1)
                    valor = (
                        None if rnd.random() < TAXA_ITEM_SEM_VALOR
                        else round(rnd.uniform(6, 900) * fator_preco + 1, 2)
                    )
                    cur.execute(
                        "INSERT INTO cadastro.item (organizacao_id, cod_item,"
                        " cod_item_cliente, descricao, grupo, subgrupo, marca, categoria,"
                        " altura_cm, largura_cm, comprimento_cm, peso_kg, multiplo_saida,"
                        " qtd_amarracao, pcs_pallet, valor_unitario)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                        " RETURNING id",
                        (
                            cli["id"], f"{cli['sigla']}{i:05d}",
                            f"{rnd.randrange(10**6, 10**8)}",
                            f"{subgrupo} {marca} {apres}",
                            grupo, subgrupo, marca,
                            rnd.choice(["Ciclo", "Linha", "Sazonal"]),
                            alt, larg, comp, peso,
                            rnd.choice([1, 1, 6, 12, 24]), rnd.choice([1, 4, 8]),
                            rnd.choice([48, 96, 144, 288]), valor,
                        ),
                    )
                    item_id = int(cur.fetchone()[0])  # type: ignore[index]
                    if estoca:
                        cur.execute(
                            "INSERT INTO cadastro.cota (item_id, nivel1, nivel2, nivel3)"
                            " VALUES (%s, %s, %s, %s)",
                            (item_id, grupo, subgrupo, marca),
                        )

    def _destinatarios(self) -> None:
        # endereços de ENTREGA por cliente, na distribuição de cidades do caso
        rnd = self.rnd
        cidades = _ler_csv("cidades.csv")
        pesos = [int(r["peso"]) for r in cidades]
        mun_por_chave = {(m["nome"], m["uf"]): m["id"] for m in self.municipios}
        with self.conn.cursor() as cur:
            for cli in self.clientes:
                n = int(self.gabarito[cli["sigla"]]["n_destinatarios"])
                for _ in range(n):
                    c = rnd.choices(cidades, weights=pesos, k=1)[0]
                    nome = (f"{rnd.choice(DESTINATARIO_SUFIXO)} "
                            f"{rnd.choice(DESTINATARIO_RADICAL)}")
                    cur.execute(
                        "INSERT INTO cadastro.endereco (organizacao_id, tipo, cnpj_local,"
                        " nome_local, logradouro, numero, bairro, municipio_id, cep)"
                        " VALUES (%s,'ENTREGA',%s,%s,%s,%s,%s,%s,%s)",
                        (
                            cli["id"], _cnpj(rnd), nome,
                            rnd.choice(["Rua", "Av.", "Travessa", "Alameda"])
                            + " " + rnd.choice(DESTINATARIO_RADICAL),
                            str(rnd.randrange(1, 9000)),
                            rnd.choice(["Centro", "Industrial", "Jardim", "Vila"]),
                            mun_por_chave[(c["cidade"], c["uf"])], _cep(rnd),
                        ),
                    )

    def _slas(self) -> None:
        rnd = self.rnd
        with self.conn.cursor() as cur:
            for cli in self.clientes:
                pre = 1 if cli["porte"] in ("MEGA", "GRANDE") else rnd.choice([1, 2])
                cur.execute(
                    "INSERT INTO cadastro.sla_manuseio (organizacao_id, hora_corte,"
                    " dias_pre_corte, dias_pos_corte, dias_pre_corte_retira,"
                    " dias_pos_corte_retira) VALUES (%s,'12:00',%s,%s,%s,%s)",
                    (cli["id"], pre, pre + 1, max(1, pre - 1), pre),
                )
            for uf in self.ufs:
                regiao = self.regiao_da_uf.get(uf, "NORTE-CENTRO-OESTE")
                d_min, d_max = DIAS_POR_REGIAO[regiao]
                for codigo, dias in (
                    ("RODO_FRAC", self.rnd.randint(d_min, d_max)),
                    ("RODO_LOT", max(1, d_min)),
                    ("AEREO", max(1, d_min // 2)),
                ):
                    cur.execute(
                        "INSERT INTO cadastro.sla_transporte (uf, municipio_id,"
                        " modalidade_id, dias_prazo) VALUES (%s, NULL, %s, %s)",
                        (uf, self.modalidade_id[codigo], dias),
                    )
            _ = rnd

    def _tarifas(self) -> None:
        rnd = self.rnd
        with self.conn.cursor() as cur:
            for cli in self.clientes:
                g = self.gabarito[cli["sigla"]]
                fator_preco = float(g["fator_preco"])
                for uf in self.ufs:
                    regiao = self.regiao_da_uf.get(uf, "NORTE-CENTRO-OESTE")
                    base = RSKG_POR_REGIAO[regiao]
                    for codigo, fator_modal in FATOR_MODAL.items():
                        cur.execute(
                            "INSERT INTO financeiro.tarifa_frete (organizacao_id,"
                            " modalidade_id, uf, faixa_peso_min, preco_teorico,"
                            " vigencia_inicio) VALUES (%s,%s,%s,0,%s,'2020-01-01')",
                            (
                                cli["id"], self.modalidade_id[codigo], uf,
                                round(base * fator_modal * (0.8 + fator_preco * 0.6)
                                      * rnd.uniform(0.95, 1.05), 3),
                            ),
                        )
                if g["estoca"] == "True":
                    cur.execute(
                        "INSERT INTO financeiro.tarifa_armazenagem (organizacao_id,"
                        " valor_m3, aliquota_ad_valorem, valor_minimo_mensal,"
                        " vigencia_inicio) VALUES (%s,%s,%s,%s,'2020-01-01')",
                        (
                            cli["id"], round(rnd.uniform(16, 24), 2),
                            round(rnd.uniform(0.0020, 0.0035), 5),
                            round(rnd.uniform(100, 250), 2),
                        ),
                    )

    def _motivos(self) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO expedicao.motivo_atraso (descricao) VALUES (%s)",
                [(m,) for m in MOTIVOS_ATRASO],
            )

    def _contagens(self) -> dict[str, int]:
        consultas = {
            "item": "cadastro.item",
            "item_sem_valor": "cadastro.item WHERE valor_unitario IS NULL",
            "cota": "cadastro.cota",
            "endereco_entrega": "cadastro.endereco WHERE tipo = 'ENTREGA'",
            "sla_manuseio": "cadastro.sla_manuseio",
            "sla_transporte": "cadastro.sla_transporte",
            "tarifa_frete": "financeiro.tarifa_frete",
            "tarifa_armazenagem": "financeiro.tarifa_armazenagem",
            "motivo_atraso": "expedicao.motivo_atraso",
        }
        saida: dict[str, int] = {}
        with self.conn.cursor() as cur:
            for nome, alvo in consultas.items():
                cur.execute(f"SELECT count(*) FROM {alvo}")  # noqa: S608
                saida[nome] = int(cur.fetchone()[0])  # type: ignore[index]
        return saida
