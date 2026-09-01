"""Etapa 4 do gerador: entrada de mercadoria, estoque e armazenagem (2020-2026).

Agendamentos de chegada (com ~9,6% de no-show, a sujeira da referência), ordens
de recebimento e itens recebidos; lotes com validade (incluindo vencidos e
datas absurdas, de propósito); movimentos de estoque (entradas dos
recebimentos e saídas dos pedidos dos clientes que estocam); posição corrente;
a FOTO OFICIAL mensal (estoque_snapshot) que sustenta a cobrança; inventários;
e o faturamento mensal de armazenagem (m³ × tarifa + ad valorem sobre o valor,
com o acréscimo de aging a partir da política de 2024-08).
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Any

import psycopg

from logistica_fictitur.gerador import SEMENTE
from logistica_fictitur.gerador.etapa1_cadastro import _ler_csv
from logistica_fictitur.gerador.etapa3_arco_pedidos import AGORA, _copy

TAXA_NO_SHOW = 0.096
TAXA_CANCELAMENTO = 0.02
FORNECEDORES = ["Fábrica Matriz do Cliente", "Importadora Litoral", "CD Regional",
                "Indústria Parceira", "Operador Anterior", "Filial Nordeste"]
TIPOS_CARGA = ["PALETIZADA", "BATIDA", "MISTA"]


class EstoqueArmazenagem:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.rnd = random.Random(SEMENTE + 4)
        self.agendamento = 500_000
        self.ordem = 700_000

    def ja_populado(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fwm.agendamento")
            linha = cur.fetchone()
            return bool(linha and int(linha[0]) > 0)

    def _carregar_mundo(self) -> None:
        rnd = self.rnd
        gab = {r["sigla"]: r for r in _ler_csv("gabarito_clientes.csv")}
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, sigla FROM cadastro.organizacao"
                " WHERE tipo_parceria = 'CLIENTE' ORDER BY id"
            )
            self.clientes: list[dict[str, Any]] = []
            for i, s in cur.fetchall():
                g = gab[str(s)]
                self.clientes.append({
                    "id": int(i), "sigla": str(s), "estoca": g["estoca"] == "True",
                    "deposito": float(g["deposito"]),
                    "base_vol": float(g["pedidos_mes_base"]),
                    # densidade de valor da mercadoria (R$/m3) — dita o ad valorem
                    "densidade": rnd.uniform(800, 4800),
                })
            cur.execute("SELECT id, galpao_id FROM cadastro.doca ORDER BY id")
            self.docas_por_galpao: dict[int, list[int]] = {}
            for did, gid in cur.fetchall():
                self.docas_por_galpao.setdefault(int(gid), []).append(int(did))
            cur.execute(
                "SELECT g.id, g.codigo, o.tipo_parceria FROM cadastro.galpao g"
                " JOIN cadastro.organizacao o ON o.id = g.organizacao_id"
            )
            todos = [(int(i), str(c), str(t)) for i, c, t in cur.fetchall()]
            self.galpoes_matriz = [i for i, _, t in todos if t == "MATRIZ"]
            self.galpoes_todos = [i for i, _, _ in todos]
            cur.execute(
                "SELECT organizacao_id, id, peso_kg, altura_cm * largura_cm * comprimento_cm"
                " / 1000000.0, valor_unitario FROM cadastro.item"
            )
            self.itens: dict[int, list[dict[str, Any]]] = {}
            for oid, iid, peso, m3, valor in cur.fetchall():
                self.itens.setdefault(int(oid), []).append(
                    {"id": int(iid), "peso": float(peso), "m3": float(m3),
                     "valor": None if valor is None else float(valor)})
            cur.execute(
                "SELECT t.organizacao_id, t.valor_m3, t.aliquota_ad_valorem,"
                " t.valor_minimo_mensal FROM financeiro.tarifa_armazenagem t"
            )
            self.tarifa = {int(o): (float(v), float(a), float(m))
                           for o, v, a, m in cur.fetchall()}
            cur.execute("SELECT id FROM cadastro.posicao_armazem")
            self.posicoes = [int(i) for (i,) in cur.fetchall()]
            cur.execute("SELECT valor FROM financeiro.parametro_financeiro"
                        " WHERE chave LIKE 'aging%'")
            self.aging_medio = 1.0 + sum(float(v) for (v,) in cur.fetchall()) / 4 * 0.18

    def executar(self) -> dict[str, int]:
        self._carregar_mundo()
        with self.conn.cursor() as cur:
            self._lotes(cur)
            for ano in range(2020, 2027):
                for mes in range(1, 13):
                    if (ano, mes) > (2026, 9):
                        break
                    self._gerar_mes(cur, ano, mes)
                self.conn.commit()
            self._saldo_e_saidas(cur)
            self._inventarios(cur)
            self.conn.commit()
        return self._contagens()

    def _lotes(self, cur: psycopg.Cursor) -> None:
        rnd = self.rnd
        linhas: list[tuple[Any, ...]] = []
        self.lotes_por_item: dict[int, list[int]] = {}
        proximo = 1
        for cli in self.clientes:
            if not cli["estoca"]:
                continue
            for item in self.itens[cli["id"]]:
                for _n in range(rnd.randint(1, 3)):
                    if rnd.random() < 0.004:      # validade absurda (sujeira)
                        validade = date(rnd.choice([2047, 2050]), rnd.randint(1, 12), 15)
                    elif rnd.random() < 0.06:     # lote vencido parado no estoque
                        validade = date(rnd.randint(2021, 2025), rnd.randint(1, 12), 20)
                    else:
                        validade = AGORA.date() + timedelta(days=rnd.randint(60, 900))
                    linhas.append((item["id"], f"L{proximo:07d}", validade,
                                   None, validade - timedelta(days=30), 30))
                    self.lotes_por_item.setdefault(item["id"], []).append(proximo)
                    proximo += 1
        _copy(cur, "fwm.lote",
              "item_id, codigo, dt_validade, dt_validade_alternativa,"
              " dt_validade_calculada, vencimento_dias_revalidacao", linhas)
        cur.execute("SELECT id, item_id FROM fwm.lote")
        self.lote_ids: dict[int, list[int]] = {}
        for lid, iid in cur.fetchall():
            self.lote_ids.setdefault(int(iid), []).append(int(lid))

    def _gerar_mes(self, cur: psycopg.Cursor, ano: int, mes: int) -> None:
        rnd = self.rnd
        fator_ano = {2020: 0.55, 2021: 0.68, 2022: 0.78, 2023: 0.90,
                     2024: 1.0, 2025: 1.12, 2026: 1.2}[ano]
        agendamentos: list[tuple[Any, ...]] = []
        ordens: list[tuple[Any, ...]] = []
        receb_itens: list[tuple[Any, ...]] = []
        movimentos: list[tuple[Any, ...]] = []
        snapshots: list[tuple[Any, ...]] = []
        faturas: list[tuple[Any, ...]] = []
        ultimo_dia = 1 if (ano, mes) == (2026, 9) else 28

        n_agnd = 0 if (ano, mes) == (2026, 9) else int(1_700 * fator_ano
                                                       * rnd.uniform(0.92, 1.08))
        estocadores = [c for c in self.clientes if c["estoca"]]
        for _ in range(n_agnd):
            cli = rnd.choices(estocadores,
                              weights=[c["base_vol"] + 60 for c in estocadores], k=1)[0]
            self.agendamento += 1
            galpao = rnd.choice(self.galpoes_matriz if rnd.random() < 0.75
                                else self.galpoes_todos)
            cadastro = datetime(ano, mes, rnd.randint(1, ultimo_dia),
                                rnd.randint(6, 18), rnd.randint(0, 59))
            prevista = cadastro + timedelta(days=rnd.randint(1, 9))
            cancelado = rnd.random() < TAXA_CANCELAMENTO
            no_show = (not cancelado) and rnd.random() < TAXA_NO_SHOW
            chegada = None if (cancelado or no_show) else (
                prevista + timedelta(minutes=int(max(-90, rnd.gauss(35, 80)))))
            peso = round(rnd.uniform(300, 12_000), 2)
            m3 = round(peso / rnd.uniform(180, 320), 3)
            agendamentos.append((
                self.agendamento, cli["id"], galpao,
                rnd.choice(self.docas_por_galpao[galpao]),
                rnd.choice(FORNECEDORES), None, f"Transp. Contratada {rnd.randint(1, 40)}",
                rnd.choice(["TRUCK", "CARRETA", "VUC"]), 2, "Recebimento padrão",
                cadastro, prevista, chegada,
                cadastro + timedelta(hours=2) if cancelado else None,
                None, "Cancelado pelo fornecedor" if cancelado else None,
                peso, round(peso * rnd.uniform(0.9, 1.3), 2), rnd.randint(10, 800),
                m3, rnd.choice(TIPOS_CARGA), None, None, None, None, None,
                rnd.random() < 0.65, 1 if chegada else (3 if cancelado else 2),
                "CONCLUIDO" if chegada else ("CANCELADO" if cancelado else "NO_SHOW"),
            ))
            if chegada is not None:
                self.ordem += 1
                ordens.append((self.ordem, self.agendamento, chegada + timedelta(hours=1),
                               f"RC{self.ordem}", 1, "FINALIZADA",
                               chegada + timedelta(hours=rnd.uniform(0.5, 6)),
                               prevista + timedelta(days=2)))
                for item in rnd.sample(self.itens[cli["id"]],
                                       k=min(len(self.itens[cli["id"]]),
                                             rnd.randint(2, 9))):
                    qtd = rnd.randint(24, 2400)
                    receb_itens.append((
                        self.ordem, item["id"], None, qtd, "D+1", "D+2",
                        chegada.date() - timedelta(days=1), chegada.date(),
                        chegada.date() + timedelta(days=rnd.randint(0, 4)), galpao,
                    ))
                    movimentos.append((item["id"],
                                       rnd.choice(self.lote_ids.get(item["id"], [None])),
                                       None, galpao, "ENTRADA", qtd, chegada, None,
                                       self.ordem, None))

        # foto mensal de fechamento + fatura de armazenagem
        fechamento = (date(ano, mes, 28) if (ano, mes) != (2026, 9)
                      else date(2026, 9, 1))
        for cli in estocadores:
            m3_cli = max(4.0, cli["deposito"] * cli["base_vol"] * 0.09
                         * fator_ano * rnd.uniform(0.85, 1.15))
            valor_cli = m3_cli * cli["densidade"]
            amostra = rnd.sample(self.itens[cli["id"]],
                                 k=min(len(self.itens[cli["id"]]), rnd.randint(8, 28)))
            quinhoes = [rnd.random() + 0.05 for _ in amostra]
            total_q = sum(quinhoes)
            for item, q in zip(amostra, quinhoes, strict=True):
                frac = q / total_q
                snapshots.append((
                    fechamento, item["id"],
                    rnd.choice(self.galpoes_matriz if rnd.random() < 0.8
                               else self.galpoes_todos),
                    max(1, int(frac * m3_cli / max(item["m3"], 0.0004))),
                    round(frac * m3_cli, 4), round(frac * valor_cli, 2),
                    round(frac * valor_cli * rnd.uniform(0, 0.02), 2),
                    rnd.choice([5, 15, 40, 75, 120, 200, 400]),
                ))
            valor_m3, adv, minimo = self.tarifa[cli["id"]]
            cobranca = m3_cli * valor_m3 + valor_cli * adv
            if date(ano, mes, 1) >= date(2024, 8, 1):
                cobranca *= self.aging_medio
            cobranca = max(cobranca, minimo)
            faturas.append((cli["id"], date(ano, mes, 1), round(m3_cli, 3),
                            round(valor_cli, 2), round(cobranca, 2),
                            fechamento + timedelta(days=3)))

        _copy(cur, "fwm.agendamento",
              "id, organizacao_id, galpao_id, doca_id, fornecedor, sub_fornecedor,"
              " transportadora, tipo_veiculo, tipo_or_id, tipo_or, dt_cadastro,"
              " dt_prevista_chegada, dt_chegada, dt_cancelamento, login_cancelamento,"
              " motivo_cancelamento, peso_geral, peso_cubado, qtde_volumes, m3, tipo_carga,"
              " capacidade, nfs, nr_coleta, batida, eo, fl_agendamento_web, status_id, status",
              agendamentos)
        _copy(cur, "fwm.ordem_recebimento",
              "id, agendamento_id, dt_or, cod_receb, status_id, status, dt_liberacao_doca,"
              " dt_prevista_fim", ordens)
        _copy(cur, "fwm.recebimento_item",
              "ordem_recebimento_id, item_id, descricao_item, quantidade, sla_recebimento,"
              " sla_cota, dt_transporte, dt_recebimento, dt_subida_cota, galpao_destino_id",
              receb_itens)
        _copy(cur, "fwm.movimento_estoque",
              "item_id, lote_id, posicao_id, galpao_id, tipo, quantidade, dt_movimento,"
              " ss, ordem_recebimento_id, inventario_id", movimentos)
        _copy(cur, "fwm.estoque_snapshot",
              "data, item_id, galpao_id, qtde_saldo, m3_ocupado, valor_material,"
              " valor_danificado, dias_sem_movimento", snapshots)
        _copy(cur, "faturamento.fatura_armazenagem",
              "organizacao_id, competencia, m3_medio, valor_material_medio, valor_cobrado,"
              " dt_faturamento", faturas)

    def _saldo_e_saidas(self, cur: psycopg.Cursor) -> None:
        # saídas: um movimento por item de pedido dos clientes que estocam
        # (clientes sem depósito operam em cross-docking, sem movimento de estoque)
        rnd = self.rnd
        estoca_ids = tuple(c["id"] for c in self.clientes if c["estoca"])
        cur.execute(
            "INSERT INTO fwm.movimento_estoque (item_id, lote_id, posicao_id, galpao_id,"
            " tipo, quantidade, dt_movimento, ss)"
            " SELECT pi.item_id, NULL, NULL, %s, 'SAIDA', -pi.quantidade,"
            "        pf.dt_entrada, pi.ss"
            " FROM fwm.pedido_item pi"
            " JOIN fwm.pedido p ON p.ss = pi.ss AND p.organizacao_id = ANY(%s)"
            " JOIN fwm.pedido_fase pf ON pf.ss = pi.ss"
            " JOIN cadastro.fase f ON f.id = pf.fase_id AND f.codigo = 'ME'",
            (rnd.choice(self.galpoes_matriz), list(estoca_ids)),
        )
        # posição corrente: derivada da última foto (o presente congelado do caso)
        cur.execute(
            "INSERT INTO fwm.estoque_saldo (item_id, lote_id, posicao_id, galpao_id,"
            " saldo, reservado, em_cota, dt_atualizacao)"
            " SELECT s.item_id, NULL,"
            "        (SELECT id FROM cadastro.posicao_armazem"
            "          WHERE galpao_id = s.galpao_id LIMIT 1),"
            "        s.galpao_id, s.qtde_saldo,"
            "        (s.qtde_saldo * 0.06)::int, (s.qtde_saldo * 0.12)::int, %s"
            " FROM fwm.estoque_snapshot s WHERE s.data = %s",
            (AGORA, AGORA.date()),
        )

    def _inventarios(self, cur: psycopg.Cursor) -> None:
        rnd = self.rnd
        inv = 0
        for galpao in self.galpoes_todos:
            for ano in range(2020, 2027):
                if rnd.random() < 0.75:
                    inv += 1
                    inicio = datetime(ano, rnd.choice([1, 6, 7, 12]),
                                      rnd.randint(2, 27), 7, 0)
                    cur.execute(
                        "INSERT INTO fwm.inventario (galpao_id, dt_criado, dt_inicio,"
                        " dt_termino, status) VALUES (%s, %s, %s, %s, 'CONCLUIDO')"
                        " RETURNING id",
                        (galpao, inicio - timedelta(days=7), inicio,
                         inicio + timedelta(days=rnd.randint(1, 3))),
                    )
        self.total_inventarios = inv

    def _contagens(self) -> dict[str, int]:
        alvos = {"agendamento": "fwm.agendamento",
                 "ordem_recebimento": "fwm.ordem_recebimento",
                 "recebimento_item": "fwm.recebimento_item", "lote": "fwm.lote",
                 "movimento_estoque": "fwm.movimento_estoque",
                 "estoque_snapshot": "fwm.estoque_snapshot",
                 "estoque_saldo": "fwm.estoque_saldo", "inventario": "fwm.inventario",
                 "fatura_armazenagem": "faturamento.fatura_armazenagem"}
        saida: dict[str, int] = {}
        with self.conn.cursor() as cur:
            for nome, alvo in alvos.items():
                cur.execute(f"SELECT count(*) FROM {alvo}")  # noqa: S608
                saida[nome] = int(cur.fetchone()[0])  # type: ignore[index]
        return saida
