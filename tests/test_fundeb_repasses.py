"""Invariantes do Fundeb 2025 (repasses efetivos) e cruzamento com o ETI."""
import pandas as pd
import pytest

from src.manifest import INTERIM


def _ler(nome):
    p = INTERIM / nome
    if not p.exists():
        pytest.skip(f"{nome} ainda não gerado")
    return pd.read_parquet(p)


def test_municipio_reconcilia_com_repasses():
    f = _ler("fundeb_municipio_2025.parquet")
    r = _ler("fundeb_repasses_2025.parquet")
    assert len(f) == 5571 and f.cod_ibge_7.is_unique
    base = r[r.componente.isin(["contribuicao", "compl_vaaf", "compl_vaat", "compl_vaar"])].valor.sum()
    assert f.vl_receita_mun.sum() + f.vl_receita_est.sum() == pytest.approx(base, abs=10)


def test_fti_igual_eti_out_a_dez():
    f = _ler("fundeb_municipio_2025.parquet").set_index("cod_ibge_7")
    e = _ler("eti_redes_2025.parquet")
    e = e[e.rede == "municipal"].set_index("cod_ibge")
    eti = e[["vl_eti_out_2025", "vl_eti_nov_2025", "vl_eti_dez_2025"]].sum(axis=1)
    fti = f.vl_fti_mun.reindex(eti.index).fillna(0)
    assert (fti - eti).abs().max() < 1
