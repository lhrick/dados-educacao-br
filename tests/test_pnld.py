"""Invariantes do PNLD municipal (rateio da UF)."""
import pandas as pd
import pytest

from src.manifest import INTERIM


def test_pnld_municipio_reconcilia():
    p = INTERIM / "pnld_municipio_2025.parquet"
    if not p.exists():
        pytest.skip("pnld_municipio_2025.parquet ainda não gerado")
    o = pd.read_parquet(p)
    u = pd.read_parquet(INTERIM / "pnld_uf_2025.parquet")
    assert len(o) == 5571 and o.cod_ibge_7.is_unique
    assert o.vl_pnld_total_est.sum() == pytest.approx(u.vl_pnld.sum(), abs=10)
    oficial = u[u.etapa_pnld.isin(["ei_literario", "ai_didatico", "af", "em"])].qtd_alunos.sum()
    assert abs(o.afetados_pnld.sum() - oficial) < 1000  # só arredondamento do rateio
