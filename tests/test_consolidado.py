"""Tabela consolidada: chaves, regras do CLAUDE.md e reconciliação com as fontes."""
import pandas as pd
import pytest

from src.manifest import INTERIM, PROCESSED


@pytest.fixture(scope="module")
def d():
    p = PROCESSED / "educacao_municipios_2025.parquet"
    if not p.exists():
        pytest.skip("consolidado ainda não gerado")
    return pd.read_parquet(p)


def test_uma_linha_por_municipio(d):
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")
    assert len(d) == len(ref) and d.cod_ibge_7.is_unique
    assert d.cod_ibge_7.str.fullmatch(r"\d{7}").all()


def test_nao_soma_alunos_entre_programas(d):
    assert not [c for c in d.columns if "total_afetados" in c or c == "afetados_total"]


def test_textos_vazios_quando_zero(d):
    assert (d.loc[d.qtd_beneficiarios_pe_de_meia.fillna(0) == 0, "txt_pe_de_meia"] == "").all()
    assert (d.loc[d.vl_fundeb_uniao_rede_municipal.fillna(0) == 0, "txt_fundeb_uniao"] == "").all()
    assert not d.txt_pe_de_meia.str.contains(r"^0 ").any()


def test_textos_so_de_valores_publicados(d):
    dic = pd.read_csv(PROCESSED / "educacao_municipios_2025_dicionario.csv", sep=";", encoding="utf-8-sig")
    tipo = dic.set_index("coluna").tipo
    for c in ["qtd_beneficiarios_pe_de_meia", "vl_fundeb_uniao_rede_municipal",
              "qtd_matriculas_eti_rede_municipal", "vl_fomento_eti_rede_municipal"]:
        assert tipo[c] != "estimativa", c


def test_reconcilia_com_intermediarias(d):
    pdm = pd.read_parquet(INTERIM / "pe_de_meia_municipio_2025.parquet")
    eti = pd.read_parquet(INTERIM / "eti_municipio_2025.parquet")
    assert d.qtd_beneficiarios_pe_de_meia.sum() == pdm.qtd_beneficiarios_pe_de_meia.sum()
    assert d.vl_fomento_eti_rede_municipal.sum() == pytest.approx(eti.vl_fomento_eti_mun.sum())


def test_explicacao_programas():
    p = PROCESSED / "programas_explicacao_2025.csv"
    if not p.exists():
        pytest.skip("explicação ainda não gerada")
    e = pd.read_csv(p, sep=";", encoding="utf-8-sig")
    assert len(e) == 4 and e.notna().all().all()
    d = pd.read_parquet(PROCESSED / "educacao_municipios_2025.parquet")
    # toda coluna citada na explicação existe no CSV consolidado
    for cols in e.colunas_no_csv:
        for c in [x.strip() for x in cols.split(",")]:
            if "/" in c:  # recebe_vaaf/vaat/vaar_rede_municipal
                continue
            assert c in d.columns, c
