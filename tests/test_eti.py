"""Invariantes do fomento ETI 2025."""
import pandas as pd
import pytest

from src.ingest.eti import TOTAL_PORTARIA_586
from src.manifest import INTERIM


def _ler(nome):
    p = INTERIM / nome
    if not p.exists():
        pytest.skip(f"{nome} ainda não gerado")
    return pd.read_parquet(p)


def test_redes_batem_com_portaria_586():
    r = _ler("eti_redes_2025.parquet")
    assert r.vl_fomento_eti.sum() == pytest.approx(TOTAL_PORTARIA_586, abs=1)
    assert not r.duplicated(["cod_ibge", "rede"]).any()
    assert (r.vl_fomento_eti >= 0).all() and (r.qtd_matriculas_eti >= 0).all()


def test_municipio_reconcilia():
    o = _ler("eti_municipio_2025.parquet")
    assert len(o) == 5571 and o.cod_ibge_7.is_unique
    assert o.vl_fomento_eti_total.sum() == pytest.approx(TOTAL_PORTARIA_586, abs=10)
