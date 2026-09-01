"""Etapa 3 do gerador: o arco operacional de pedidos (2020-01 a 2026-09-01 08h).

Gera, mês a mês e via COPY (volume na casa dos milhões): pedidos com o mix de
clientes do gabarito, itens, histórico de fases (EA..CE), minutas, NFs,
entregas com a CURVA DA HISTÓRIA (2020 ruim, oscilação até 2023, virada do
novo VP no 2º semestre de 2024, excelência em 2025-26), ocorrências,
faturas de frete e custos variáveis (CUSTO_FRETE e DEV_REENTREGA).

Sujeira plantada aqui: datas-sentinela na entrega (~0,5%: 1899-12-30 e futuros
absurdos) e o frete simbólico de R$ 0,01 nas retiradas.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Any

import psycopg

from logistica_fictitur.gerador import SEMENTE
from logistica_fictitur.gerador.etapa1_cadastro import NOMES, SOBRENOMES, _ler_csv

AGORA = datetime(2026, 9, 1, 8, 0)

# média-alvo de pedidos/mês por ano (centro das bandas da régua)
ALVO_MES = {2020: 7_700, 2021: 9_700, 2022: 11_000, 2023: 13_000,
            2024: 15_200, 2025: 17_200, 2026: 18_400}
SAZONALIDADE = [0.86, 0.84, 1.02, 0.97, 1.00, 1.03, 1.01, 1.08, 1.06, 1.10, 1.16, 0.87]

# OTIF-base por ano; em 2024 a virada é intra-ano (rampa no 2º semestre)
OTIF_BASE = {2020: 0.820, 2021: 0.828, 2022: 0.812, 2023: 0.836,
             2024: 0.845, 2025: 0.965, 2026: 0.972}
# quanto o viés individual do cliente ainda pesa (o VP comprime a dispersão)
FATOR_VIES = {2020: 1.0, 2021: 1.0, 2022: 1.0, 2023: 1.0, 2024: 0.6, 2025: 0.25, 2026: 0.2}

MODAL_MIX = [("RODO_FRAC", 55), ("RETIRA", 12), ("RODO_LOT", 8), ("EXCLUSIVO", 6),
             ("REDESPACHO", 6), ("LOCAL", 6), ("AEREO", 5), ("TRANSF_BASE", 1),
             ("DEVOLUCAO", 1)]
VEICULOS = ["FIORINO", "VUC", "TOCO", "TRUCK", "CARRETA"]
TAXA_SENTINELA = 0.005
SENTINELAS = [datetime(1899, 12, 30), datetime(2055, 8, 11), datetime(2098, 8, 22)]
PEDIDOS_POR_MINUTA = 22


def _copy(cur: psycopg.Cursor, tabela: str, colunas: str, linhas: list[tuple[Any, ...]]) -> None:
    if not linhas:
        return
    with cur.copy(f"COPY {tabela} ({colunas}) FROM STDIN") as cp:
        for linha in linhas:
            cp.write_row(linha)


class ArcoPedidos:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.rnd = random.Random(SEMENTE + 3)
        self.ss = 3_000_000
        self.nf = 800_000
        self.minuta = 400_000

    def ja_populado(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fwm.pedido")
            linha = cur.fetchone()
            return bool(linha and int(linha[0]) > 0)

    # -- preparação -------------------------------------------------------

    def _carregar_mundo(self) -> None:
        rnd = self.rnd
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, codigo FROM cadastro.fase ORDER BY ordem")
            self.fase_id = {str(c): int(i) for i, c in cur.fetchall()}
            cur.execute("SELECT id, codigo FROM cadastro.modalidade")
            self.modal_id = {str(c): int(i) for i, c in cur.fetchall()}
            cur.execute("SELECT id FROM cadastro.transportador")
            self.transportadores = [int(i) for (i,) in cur.fetchall()]
            cur.execute("SELECT id FROM expedicao.motivo_atraso")
            self.motivos = [int(i) for (i,) in cur.fetchall()]
            cur.execute("SELECT id FROM cadastro.representante")
            self.representantes = [int(i) for (i,) in cur.fetchall()]
            cur.execute("SELECT id FROM cadastro.usuario")
            self.usuarios = [int(i) for (i,) in cur.fetchall()]
            cur.execute(
                "SELECT o.id, o.sigla, o.porte, o.fl_entrega_agendada, o.dt_cancelamento"
                " FROM cadastro.organizacao o WHERE o.tipo_parceria = 'CLIENTE'"
            )
            self.clientes = [
                {"id": int(i), "sigla": str(s), "porte": str(p),
                 "agendada": bool(a), "cancelado": c}
                for i, s, p, a, c in cur.fetchall()
            ]
            cur.execute(
                "SELECT e.id, e.organizacao_id, m.nome, m.uf, e.cep, e.nome_local"
                " FROM cadastro.endereco e JOIN cadastro.municipio m ON m.id = e.municipio_id"
                " WHERE e.tipo = 'ENTREGA'"
            )
            self.enderecos: dict[int, list[tuple[int, str, str, str, str]]] = {}
            for eid, oid, cidade, uf, cep, nome in cur.fetchall():
                self.enderecos.setdefault(int(oid), []).append(
                    (int(eid), str(cidade), str(uf), str(cep), str(nome))
                )
            cur.execute(
                "SELECT organizacao_id, id, peso_kg, altura_cm, largura_cm, comprimento_cm,"
                " valor_unitario, multiplo_saida, descricao FROM cadastro.item"
            )
            self.itens: dict[int, list[dict[str, Any]]] = {}
            for oid, iid, peso, alt, larg, comp, valor, mult, desc in cur.fetchall():
                m3 = float(alt) * float(larg) * float(comp) / 1_000_000
                self.itens.setdefault(int(oid), []).append(
                    {"id": int(iid), "peso": float(peso), "m3": m3,
                     "valor": None if valor is None else float(valor),
                     "mult": int(mult), "desc": str(desc)}
                )
            cur.execute("SELECT organizacao_id, dias_pre_corte FROM cadastro.sla_manuseio")
            self.dias_manuseio = {int(o): int(d) for o, d in cur.fetchall()}
            cur.execute(
                "SELECT s.uf, m.codigo, s.dias_prazo FROM cadastro.sla_transporte s"
                " JOIN cadastro.modalidade m ON m.id = s.modalidade_id"
            )
            self.dias_transporte = {(str(u), str(c)): int(d) for u, c, d in cur.fetchall()}
            cur.execute(
                "SELECT t.organizacao_id, m.codigo, t.uf, t.preco_teorico"
                " FROM financeiro.tarifa_frete t"
                " JOIN cadastro.modalidade m ON m.id = t.modalidade_id"
            )
            self.tarifa = {(int(o), str(c), str(u)): float(p) for o, c, u, p in cur.fetchall()}

        gab = {r["sigla"]: r for r in _ler_csv("gabarito_clientes.csv")}
        pesos_cli: list[float] = []
        for cli in self.clientes:
            base = float(gab[cli["sigla"]]["pedidos_mes_base"])
            if cli["porte"] == "MEGA":
                base *= 1.35  # concentra o topo (banda: top 5 com 50-75% do volume)
            cli["fator_custo"] = float(gab[cli["sigla"]]["fator_custo"])
            pesos_cli.append(base)
        self.pesos_cli = pesos_cli
        # clientes-problema de 2020: volume médio-baixo, OTIF despencando até ~50%
        candidatos = [i for i, c in enumerate(self.clientes)
                      if 85 <= float(gab[c["sigla"]]["pedidos_mes_base"]) <= 500]
        problema = set(rnd.sample(candidatos, k=min(8, len(candidatos))))
        for i, cli in enumerate(self.clientes):
            if i in problema:
                cli["vies"] = -rnd.uniform(0.28, 0.34)
            elif cli["porte"] in ("MEGA", "GRANDE"):
                cli["vies"] = rnd.uniform(0.01, 0.03)
            else:
                cli["vies"] = rnd.uniform(-0.06, 0.02)
        self.pessoas = [f"{n} {s}" for n in NOMES for s in SOBRENOMES]

    # -- geração ----------------------------------------------------------

    def executar(self) -> dict[str, int]:
        self._carregar_mundo()
        with self.conn.cursor() as cur:
            for ano in range(2020, 2027):
                for mes in range(1, 13):
                    if (ano, mes) > (2026, 9):
                        break
                    self._gerar_mes(cur, ano, mes)
                self.conn.commit()
        return self._contagens()

    def _sortear_modal(self) -> str:
        return self.rnd.choices([m for m, _ in MODAL_MIX],
                                weights=[p for _, p in MODAL_MIX], k=1)[0]

    def _otif_prob(self, ano: int, mes: int, vies: float) -> float:
        base = OTIF_BASE[ano]
        if ano == 2024 and mes >= 7:
            base += 0.10 * (mes - 6) / 6  # a rampa do novo VP
        return min(0.995, max(0.44, base + vies * FATOR_VIES[ano]))

    def _gerar_mes(self, cur: psycopg.Cursor, ano: int, mes: int) -> None:
        rnd = self.rnd
        if (ano, mes) == (2026, 9):
            n_mes = 620  # só a manhã do dia corrente
        else:
            n_mes = int(ALVO_MES[ano] * SAZONALIDADE[mes - 1] * rnd.uniform(0.97, 1.03))
        pedidos: list[tuple[Any, ...]] = []
        itens: list[tuple[Any, ...]] = []
        fases: list[tuple[Any, ...]] = []
        entregas: list[tuple[Any, ...]] = []
        ocorrencias: list[tuple[Any, ...]] = []
        nfs: list[tuple[Any, ...]] = []
        minutas: list[tuple[Any, ...]] = []
        minuta_ped: list[tuple[Any, ...]] = []
        faturas: list[tuple[Any, ...]] = []
        custos: list[tuple[Any, ...]] = []
        minuta_aberta: tuple[int, int] | None = None  # (id, vagas)

        idx_clientes = rnd.choices(range(len(self.clientes)), weights=self.pesos_cli, k=n_mes)
        for idx in sorted(idx_clientes):
            cli = self.clientes[idx]
            if cli["cancelado"] and date(ano, mes, 1) > cli["cancelado"]:
                cli = self.clientes[(idx + 1) % len(self.clientes)]  # herda o volume
            self.ss += 1
            ss = self.ss
            dia_max = 1 if (ano, mes) == (2026, 9) else 28
            solicitacao = datetime(ano, mes, rnd.randint(1, dia_max),
                                   rnd.randint(7, 19), rnd.randint(0, 59))
            if (ano, mes) == (2026, 9):
                solicitacao = solicitacao.replace(hour=rnd.randint(6, 7))
            modal = self._sortear_modal()
            destino = rnd.choice(self.enderecos[cli["id"]])
            end_id, cidade, uf, cep, destinatario = destino

            # itens do pedido
            n_itens = min(len(self.itens[cli["id"]]),
                          max(1, int(rnd.gauss(4.7, 2.8))))
            valor_pedido = 0.0
            peso, m3 = 0.0, 0.0
            for item in rnd.sample(self.itens[cli["id"]], k=n_itens):
                qtd = item["mult"] * rnd.randint(1, 6)
                vu = item["valor"]
                vt = None if vu is None else round(vu * qtd, 2)
                valor_pedido += vt or 0.0
                peso += item["peso"] * qtd
                m3 += item["m3"] * qtd
                itens.append((ss, item["id"], item["desc"], qtd, vu, vt))

            # linha do tempo de fases
            em_voo = (AGORA - solicitacao) < timedelta(days=10) and rnd.random() < 0.55
            roteiro = ["EA", "PC"]
            if rnd.random() < 0.80:
                roteiro.append("DC")
            roteiro.append("PL")
            if rnd.random() < 0.30:
                roteiro.append("EX")
            roteiro += ["CF", "ME", "EN", "EC"]
            if em_voo:
                roteiro = roteiro[: rnd.randint(1, len(roteiro) - 2)]
            marcos: dict[str, datetime] = {}
            t = solicitacao
            for codigo in roteiro:
                marcos[codigo] = t
                t += timedelta(hours=rnd.uniform(2, 20))
            entregue = not em_voo
            fase_atual = roteiro[-1]

            # prazos e o veredito OTIF
            dias_uteis = self.dias_manuseio[cli["id"]] + (1 if solicitacao.hour > 12 else 0)
            transporte = self.dias_transporte.get(
                (uf, modal if modal in ("RODO_LOT", "AEREO") else "RODO_FRAC"), 4)
            prazo = (solicitacao + timedelta(days=dias_uteis + transporte + 2)).date()
            dt_entrega: datetime | None = None
            atrasou = False
            if entregue:
                no_prazo = rnd.random() < self._otif_prob(ano, mes, float(cli["vies"]))
                if no_prazo:
                    dt_entrega = datetime.combine(
                        prazo - timedelta(days=rnd.randint(0, 2)), solicitacao.time())
                else:
                    atrasou = True
                    dt_entrega = datetime.combine(
                        prazo + timedelta(days=max(1, int(rnd.gauss(4, 3)))),
                        solicitacao.time())
                if rnd.random() < TAXA_SENTINELA:
                    dt_entrega = rnd.choice(SENTINELAS)
                marcos["EC"] = dt_entrega
            codigos = list(marcos)
            for pos, codigo in enumerate(codigos):
                saida = marcos[codigos[pos + 1]] if pos + 1 < len(codigos) else (
                    dt_entrega if codigo == "EC" else None)
                fases.append((ss, self.fase_id[codigo], marcos[codigo], saida,
                              rnd.choice(self.usuarios)))

            pedidos.append((
                ss, cli["id"], rnd.choice(self.usuarios), rnd.choice(self.usuarios),
                rnd.choices(["API", "GRADE", "WEB", "OUTROS"], weights=[45, 30, 22, 3])[0],
                end_id, destinatario, rnd.choice(self.pessoas), cidade, uf, cep,
                self.modal_id[modal], rnd.choice(self.representantes),
                None, rnd.choice(["LOJA", "BASE", "DISTRIBUIDOR", "REPS"]),
                rnd.random() < 0.03, False, cli["agendada"],
                str(rnd.randrange(10**5, 10**7)) if rnd.random() < 0.6 else None,
                round(valor_pedido, 2), solicitacao, self.fase_id[fase_atual],
                rnd.randint(1, 3), None,
            ))

            if entregue and dt_entrega is not None:
                agendada = cli["agendada"] and rnd.random() < 0.8
                canhoto_ok = rnd.random() < (0.97 if ano >= 2025 else 0.90)
                entregas.append((
                    ss, prazo, prazo - timedelta(days=1),
                    prazo + timedelta(days=rnd.choice([-1, 0, 0, 1])),
                    prazo if agendada else None, dt_entrega,
                    rnd.choice(self.pessoas), canhoto_ok,
                    rnd.choice(self.motivos) if atrasou else None,
                ))
                if atrasou and rnd.random() < 0.6:
                    ocorrencias.append((ss, dt_entrega - timedelta(days=1), "OCORRENCIA",
                                        "Ocorrência de transporte", rnd.choice(self.motivos)))
                taxa_dev = 0.008 if ano >= 2025 else 0.02
                if rnd.random() < taxa_dev:
                    ocorrencias.append((ss, dt_entrega + timedelta(days=2),
                                        rnd.choice(["DEVOLUCAO", "REENTREGA"]),
                                        "Retorno de mercadoria", rnd.choice(self.motivos)))
                    custos.append((cli["id"], "DEV_REENTREGA", ss,
                                   round(30 + peso * 0.9, 2),
                                   _competencia(dt_entrega + timedelta(days=32)),
                                   (dt_entrega + timedelta(days=32)).date()))
                if "EN" in marcos:
                    self.nf += 1
                    nfs.append((self.nf, ss, marcos["EN"], round(valor_pedido, 2)))
                # minuta (retira não roda em veículo)
                if modal != "RETIRA":
                    if minuta_aberta is None or minuta_aberta[1] <= 0:
                        self.minuta += 1
                        exped = marcos.get("EN", solicitacao) + timedelta(hours=8)
                        minutas.append((
                            self.minuta, exped - timedelta(hours=10), exped,
                            rnd.choice(self.transportadores),
                            rnd.randint(1, 8) if modal == "REDESPACHO" else None,
                            rnd.choice(VEICULOS),
                            f"{rnd.choice('ABCDEFG')}{rnd.choice('LMNOP')}"
                            f"{rnd.choice('RSTUV')}{rnd.randrange(10)}"
                            f"{rnd.choice('A0')}{rnd.randrange(10)}{rnd.randrange(10)}",
                            f"R-{uf}",
                            "EXCLUSIVA" if modal == "EXCLUSIVO" else "CONSOLIDADA",
                        ))
                        minuta_aberta = (self.minuta, PEDIDOS_POR_MINUTA)
                    minuta_ped.append((minuta_aberta[0], ss))
                    minuta_aberta = (minuta_aberta[0], minuta_aberta[1] - 1)

                # fatura de frete + custo do transportador
                if modal == "RETIRA":
                    receita = 0.01
                else:
                    rskg = self.tarifa.get(
                        (cli["id"],
                         modal if modal in ("RODO_LOT", "AEREO") else "RODO_FRAC", uf), 1.5)
                    peso_taxado = max(peso, m3 * 300)
                    receita = max(18.0, peso_taxado * rskg)
                icms = receita * (0.12 if uf == "SP" else 0.07)
                dt_fat = (dt_entrega + timedelta(days=rnd.randint(3, 12)))
                if not (2019 < dt_fat.year < 2028):
                    dt_fat = datetime.combine(prazo, solicitacao.time())
                faturas.append((
                    cli["id"], ss, modal, None, round(receita - icms, 2), round(receita, 2),
                    round(max(peso, m3 * 300), 3), False, dt_fat.date(),
                    dt_fat.date() + timedelta(days=2), _competencia(dt_fat),
                ))
                if modal != "RETIRA":
                    frac = min(0.45, 0.33 * float(cli["fator_custo"])) * rnd.uniform(0.9, 1.1)
                    custos.append((cli["id"], "CUSTO_FRETE", ss, round(receita * frac, 2),
                                   _competencia(dt_fat), dt_fat.date()))

        _copy(cur, "fwm.pedido",
              "ss, organizacao_id, solicitante_id, usuario_id, origem, endereco_entrega_id,"
              " destinatario, aos_cuidados, cidade, uf, cep, modalidade_id, representante_id,"
              " campanha, tipo_destino, fl_impreterivel, fl_base, fl_entrega_agendada,"
              " nf_cliente, valor_orcamento, dt_solicitacao, fase_id, qtde_ocam, departamento",
              pedidos)
        _copy(cur, "fwm.pedido_item",
              "ss, item_id, descricao_item, quantidade, valor_unitario, valor_total", itens)
        _copy(cur, "fwm.pedido_fase", "ss, fase_id, dt_entrada, dt_saida, usuario_id", fases)
        _copy(cur, "expedicao.entrega",
              "ss, prazo_inicial_cliente, prazo_interno, dt_real_prevista, dt_agendamento,"
              " dt_entrega, recebedor, fl_canhoto, motivo_atraso_id", entregas)
        _copy(cur, "expedicao.ocorrencia_entrega",
              "ss, dt, tipo, descricao, motivo_atraso_id", ocorrencias)
        _copy(cur, "fwm.nf", "numero, ss, dt_emissao, valor", nfs)
        _copy(cur, "expedicao.minuta",
              "id, dt_criacao, dt_expedicao, transportador_id, parceiro_redespacho_id,"
              " tipo_veiculo, placa, rota, tipo_carga", minutas)
        _copy(cur, "expedicao.minuta_pedido", "minuta_id, ss", minuta_ped)
        _copy(cur, "faturamento.fatura_frete",
              "organizacao_id, ss, modal, tipo_destino, valor_frete, valor_frete_icms,"
              " peso_faturado, fl_dev_reentrega, dt_faturamento, dt_liberacao, competencia",
              faturas)
        _copy(cur, "financeiro.custo_operacao",
              "organizacao_id, categoria, ss, valor, competencia, dt_lancamento", custos)

    def _contagens(self) -> dict[str, int]:
        alvos = {"pedido": "fwm.pedido", "pedido_item": "fwm.pedido_item",
                 "pedido_fase": "fwm.pedido_fase", "nf": "fwm.nf",
                 "entrega": "expedicao.entrega", "minuta": "expedicao.minuta",
                 "ocorrencia": "expedicao.ocorrencia_entrega",
                 "fatura_frete": "faturamento.fatura_frete",
                 "custo_operacao": "financeiro.custo_operacao"}
        saida: dict[str, int] = {}
        with self.conn.cursor() as cur:
            for nome, alvo in alvos.items():
                cur.execute(f"SELECT count(*) FROM {alvo}")  # noqa: S608
                saida[nome] = int(cur.fetchone()[0])  # type: ignore[index]
        return saida


def _competencia(dt: datetime) -> date:
    return date(dt.year, dt.month, 1)
