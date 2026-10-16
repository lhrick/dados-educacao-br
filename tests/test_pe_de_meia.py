"""Invariantes da tabela municipal do Pé-de-Meia."""
import pandas as pd
import pytest

from src.manifest import INTERIM
from src.transform.pe_de_meia import ANO_PADRAO, _ano_do_periodo


def _ler(nome):
    p = INTERIM / nome
    if not p.exists():
        pytest.skip(f"{nome} ainda não gerado")
    return pd.read_parquet(p)


def test_ano_do_periodo():
    s = pd.Series(["Ano letivo 2025", "Março 2025", "Julho/Agosto 2024"])
    assert _ano_do_periodo(s).tolist() == [2025, 2025, 2024]


def test_municipio_reconcilia_com_parcelas():
    d = _ler(f"pe_de_meia_municipio_{ANO_PADRAO}.parquet")
    p = _ler("pe_de_meia_parcelas.parquet")
    p = p[_ano_do_periodo(p.periodo_incentivo) == ANO_PADRAO]
    m = _ler("ref_municipios.parquet")

    assert len(d) == len(m) and d.cod_ibge_7.is_unique
    assert d.qtd_beneficiarios_pe_de_meia.sum() == p[p.tipo_incentivo == "Matrícula"].qtd_parcelas.sum()
    assert d.vl_pago_pe_de_meia.sum() == pytest.approx(p.vl_parcelas.sum())
    assert (d.filter(like="vl_").fillna(0) >= 0).all().all()
    assert d.ano_ref.eq(ANO_PADRAO).all()
    # sem beneficiário => sem valor por aluno (nunca divisão por zero)
    assert d.loc[d.qtd_beneficiarios_pe_de_meia == 0, "vl_por_aluno_pe_de_meia"].isna().all()
