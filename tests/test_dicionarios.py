"""Toda tabela gerada precisa de dicionário em sincronia com as colunas reais."""
import pandas as pd
import pytest

from src import dicionario
from src.ingest import censo_escolar, eti, fundeb, fundeb_repasses, ibge, pe_de_meia, pnld
from src.manifest import INTERIM, PROCESSED
from src.transform import fundeb as t_fundeb
from src.transform import pe_de_meia as t_pdm
from src.transform import eti as t_eti
from src.transform import fundeb_repasses as t_fundeb_rep
from src.transform import pnld as t_pnld

CASOS = [
    (INTERIM / "ref_municipios.parquet", lambda: ibge.DICIONARIO),
    (INTERIM / "ref_escolas.parquet", lambda: censo_escolar.dicionarios(censo_escolar.ANO_PADRAO)[0]),
    (INTERIM / "ref_matriculas_municipio.parquet", lambda: censo_escolar.dicionarios(censo_escolar.ANO_PADRAO)[1]),
    (INTERIM / "pe_de_meia_parcelas.parquet", lambda: pe_de_meia.DICIONARIO),
    (INTERIM / "pe_de_meia_municipio_2025.parquet", lambda: t_pdm.dicionario_(2025)),
    (INTERIM / "fundeb_entes_2026.parquet", lambda: fundeb.DICIONARIO),
    (INTERIM / "fundeb_municipio_2026.parquet", t_fundeb.dicionario_),
    (INTERIM / "pnld_uf_2025.parquet", lambda: pnld.DICIONARIO),
    (INTERIM / "pnld_municipio_2025.parquet", t_pnld.dicionario_),
    (INTERIM / "eti_redes_2025.parquet", lambda: eti.DICIONARIO),
    (INTERIM / "eti_municipio_2025.parquet", t_eti.dicionario_),
    (INTERIM / "fundeb_repasses_2025.parquet", lambda: fundeb_repasses.DICIONARIO),
    (INTERIM / "fundeb_municipio_2025.parquet", lambda: t_fundeb_rep.dicionario_(2025)),
    (PROCESSED / "educacao_municipios_2025.parquet", None),
]


@pytest.mark.parametrize("arquivo,dic", CASOS, ids=[c[0].stem for c in CASOS])
def test_parquet_tem_dicionario(arquivo, dic):
    if not arquivo.exists():
        pytest.skip(f"{arquivo.name} ainda não gerado")
    df = pd.read_parquet(arquivo)
    if dic is not None:  # consolidado: dicionário montado dos parciais, conferido pelo arquivo salvo
        dicionario.validar(df, dic(), arquivo.stem)
    salvo = arquivo.with_name(f"{arquivo.stem}_dicionario.csv")
    assert salvo.exists(), f"falta {salvo.name}"
    assert pd.read_csv(salvo, sep=";", encoding="utf-8-sig").coluna.tolist() == list(df.columns)


@pytest.mark.parametrize("csv", sorted(p for p in PROCESSED.glob("*.csv") if not p.stem.endswith("_dicionario")),
                         ids=lambda p: p.stem)
def test_csv_processed_tem_dicionario(csv):
    cols = pd.read_csv(csv, sep=";", encoding="utf-8-sig", nrows=0).columns.tolist()
    d = pd.read_csv(csv.with_name(f"{csv.stem}_dicionario.csv"), sep=";", encoding="utf-8-sig")
    assert d.coluna.tolist() == cols
    assert d.descricao.notna().all() and d.fonte.notna().all()
    assert set(d.tipo) <= dicionario.TIPOS
