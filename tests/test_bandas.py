"""Sanidade das bandas: o contrato precisa ser internamente coerente."""

from logistica_fictitur.validacao import bandas


def _todas_as_bandas() -> list[tuple[str, bandas.Banda]]:
    saida: list[tuple[str, bandas.Banda]] = []
    for nome, valor in vars(bandas).items():
        if nome.startswith("_"):
            continue
        if isinstance(valor, tuple) and len(valor) == 2:
            saida.append((nome, valor))
        elif isinstance(valor, dict):
            saida.extend((f"{nome}[{k}]", v) for k, v in valor.items())
    return saida


def test_minimo_nao_excede_maximo() -> None:
    for nome, (minimo, maximo) in _todas_as_bandas():
        assert minimo <= maximo, nome


def test_arco_cobre_2020_a_2026() -> None:
    anos = set(range(2020, 2027))
    assert set(bandas.PEDIDOS_MES_POR_ANO) == anos
    assert set(bandas.OTIF_POR_ANO) == anos


def test_arco_otif_melhora_apos_virada() -> None:
    assert bandas.OTIF_POR_ANO[2025][0] > bandas.OTIF_POR_ANO[2023][1]


def test_volumes_crescem_ao_longo_do_arco() -> None:
    minimos = [bandas.PEDIDOS_MES_POR_ANO[a][0] for a in sorted(bandas.PEDIDOS_MES_POR_ANO)]
    assert minimos == sorted(minimos)
