"""Invariantes da tabela de entes do Fundeb 2026."""
import pandas as pd
import pytest

from src.ingest.fundeb import _num
from src.manifest import INTERIM


def test_num_formatos_fnde():
    s = pd.Series([" 18.707.652,69 ", " -   ", "53,50%", "0,000132089979", None])
    assert _num(s).tolist() == [18707652.69, 0.0, 53.5, 0.000132089979, 0.0]


def test_entes():
    p = INTERIM / "fundeb_entes_2026.parquet"
    if not p.exists():
        pytest.skip("fundeb_entes_2026.parquet ainda não gerado")
    e = pd.read_parquet(p)
    assert e.cod_ibge.is_unique
    assert e.groupby("tipo_ente").size().to_dict() == {"estado": 27, "municipio": 5569}
    assert e.vl_receita_total.sum() == pytest.approx(370_536_601_565.07, abs=1)
    assert e.vl_compl_uniao.sum() == pytest.approx(69_287_331_999.92, abs=1)
    assert ((e.vl_contribuicao_ente + e.vl_compl_uniao - e.vl_receita_total).abs() < 0.05).all()
    assert e.pct_uniao.between(0, 1).all()


def test_municipio_reconcilia():
    p = INTERIM / "fundeb_municipio_2026.parquet"
    if not p.exists():
        pytest.skip("fundeb_municipio_2026.parquet ainda não gerado")
    o = pd.read_parquet(p)
    e = pd.read_parquet(INTERIM / "fundeb_entes_2026.parquet")
    assert o.cod_ibge_7.is_unique and len(o) == 5571
    # municipal publicado + estadual rateado = total nacional do Anexo I
    total = o.vl_receita_total_mun.sum() + o.vl_receita_total_est.sum()
    assert total == pytest.approx(e.vl_receita_total.sum(), abs=10)
    assert o.perda_fundeb_sem_uniao.sum() == pytest.approx(e.vl_compl_uniao.sum(), abs=10)
    # rateio por UF fecha com o governo estadual
    est = e[e.tipo_ente == "estado"].set_index("uf").vl_receita_total
    rat = o.groupby("uf").vl_receita_total_est.sum()
    assert (rat - est.reindex(rat.index)).abs().max() < 1

