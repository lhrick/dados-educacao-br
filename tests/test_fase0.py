"""Checagens das tabelas de referência da Fase 0 (rodar depois da ingestão)."""
import pandas as pd
import pytest

from src.ingest.ibge import N_MUNICIPIOS
from src.manifest import INTERIM, MANIFEST, sha256, ROOT


def _ler(nome):
    p = INTERIM / nome
    if not p.exists():
        pytest.skip(f"{nome} ainda não gerado")
    return pd.read_parquet(p)


def test_municipios():
    m = _ler("ref_municipios.parquet")
    assert len(m) == N_MUNICIPIOS
    assert m.cod_ibge_7.is_unique
    assert m.cod_ibge_7.str.fullmatch(r"\d{7}").all()
    assert (m.cod_ibge_6 == m.cod_ibge_7.str[:6]).all()
    assert m.uf.nunique() == 27


def test_escolas():
    e = _ler("ref_escolas.parquet")
    m = _ler("ref_municipios.parquet")
    assert e.co_entidade.is_unique
    assert e.co_entidade.str.fullmatch(r"\d{8}").all()
    assert e.cod_ibge_7.isin(m.cod_ibge_7).all()
    assert set(e.rede) <= {"federal", "estadual", "municipal", "privada"}
    assert e.ano_ref.nunique() == 1


def test_matriculas_municipio_bate_com_escolas():
    e = _ler("ref_escolas.parquet")
    a = _ler("ref_matriculas_municipio.parquet")
    assert not a.duplicated(["cod_ibge_7", "rede"]).any()
    assert a.qt_mat_bas.sum() == e.qt_mat_bas.sum()
    assert a.n_escolas.sum() == len(e)


def test_manifest_hashes():
    if not MANIFEST.exists():
        pytest.skip("manifest ainda não gerado")
    man = pd.read_csv(MANIFEST, dtype=str)
    for _, r in man.iterrows():
        assert sha256(ROOT / r.arquivo) == r.hash_sha256, r.arquivo


def test_pe_de_meia_parcelas():
    p = _ler("pe_de_meia_parcelas.parquet")
    m = _ler("ref_municipios.parquet")
    assert p.cod_ibge_7.isin(m.cod_ibge_7).all()
    assert p.cod_ibge_7.str.fullmatch(r"\d{7}").all()
    # nenhuma coluna pessoal pode chegar ao interim
    assert not [c for c in p.columns if any(s in c.lower() for s in ("cpf", "nis", "nome"))]
    assert ((p.qtd_parcelas + p.qtd_estornos) > 0).all()
    assert p.loc[p.tipo_incentivo == "Matrícula", "qtd_estornos"].sum() == 0
