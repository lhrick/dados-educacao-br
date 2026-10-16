"""Fase 0.2 — Censo Escolar (INEP), microdados por escola.

Saídas:
    data/interim/ref_escolas.parquet               (uma linha por escola em atividade)
    data/interim/ref_matriculas_municipio.parquet  (cod_ibge_7 × rede)

Schema confirmado no dicionário do Censo 2024 (ver docs/fontes.md).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import zipfile

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.manifest import INTERIM, RAW, baixar

URL = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip"
ANO_PADRAO = 2024  # mais recente publicado em 2026-10-15 (2025 retorna 404)

REDES = {"1": "federal", "2": "estadual", "3": "municipal", "4": "privada"}
EM_ATIVIDADE = "1"

MATRICULAS = [
    "QT_MAT_BAS",
    "QT_MAT_INF", "QT_MAT_INF_CRE", "QT_MAT_INF_PRE",
    "QT_MAT_FUND", "QT_MAT_FUND_AI", "QT_MAT_FUND_AF",
    "QT_MAT_MED", "QT_MAT_MED_PROP", "QT_MAT_MED_CT", "QT_MAT_MED_NM",
    "QT_MAT_PROF", "QT_MAT_EJA", "QT_MAT_EJA_FUND", "QT_MAT_EJA_MED", "QT_MAT_ESP",
    "QT_MAT_INF_INT", "QT_MAT_INF_CRE_INT", "QT_MAT_INF_PRE_INT",
    "QT_MAT_FUND_INT", "QT_MAT_FUND_AI_INT", "QT_MAT_FUND_AF_INT",
    "QT_MAT_MED_INT",
]
CHAVES = [
    "NU_ANO_CENSO", "CO_MUNICIPIO", "SG_UF", "CO_ENTIDADE", "NO_ENTIDADE",
    "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO",
]


def _membros(zf: zipfile.ZipFile, ano: int) -> tuple[str, str]:
    nome_csv = f"microdados_ed_basica_{ano}.csv"
    csv = [n for n in zf.namelist() if n.endswith("/dados/" + nome_csv)]
    md5 = [n for n in zf.namelist() if n.endswith(f"/dados/md5_microdados_ed_basica_{ano}.txt")]
    if len(csv) != 1:
        raise FileNotFoundError(f"{nome_csv} não encontrado (ou duplicado) no zip")
    return csv[0], (md5[0] if md5 else "")


def _confere_md5(zf: zipfile.ZipFile, membro_csv: str, membro_md5: str) -> None:
    if not membro_md5:
        return
    nome = membro_csv.rsplit("/", 1)[-1]
    esperado = None
    for linha in zf.read(membro_md5).decode("latin-1").splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1].lstrip("*") == nome:
            esperado = partes[0].lower()
    if esperado is None:
        return
    h = hashlib.md5()
    with zf.open(membro_csv) as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != esperado:
        raise ValueError(f"MD5 de {nome} não confere com o publicado pelo INEP")


def ler_escolas(ano: int) -> pd.DataFrame:
    zpath = RAW / "inep" / f"microdados_censo_escolar_{ano}.zip"
    baixar("INEP Censo Escolar microdados", URL.format(ano=ano), zpath, ano_ref=ano)

    with zipfile.ZipFile(zpath) as zf:
        membro_csv, membro_md5 = _membros(zf, ano)
        _confere_md5(zf, membro_csv, membro_md5)
        with zf.open(membro_csv) as f:
            df = pd.read_csv(
                f, sep=";", encoding="latin-1", usecols=CHAVES + MATRICULAS, dtype=str
            )

    assert (df["NU_ANO_CENSO"] == str(ano)).all()
    df = df[df["TP_SITUACAO_FUNCIONAMENTO"] == EM_ATIVIDADE].copy()

    # Escolas ativas sem turma de escolarização (só atividade complementar/AEE)
    # vêm com matrícula nula: tratamos como zero.
    for c in MATRICULAS:
        df[c] = pd.to_numeric(df[c]).fillna(0).astype("int64")

    out = pd.DataFrame({
        "cod_ibge_7": df["CO_MUNICIPIO"].str.zfill(7),
        "co_entidade": df["CO_ENTIDADE"].str.zfill(8),
        "no_entidade": df["NO_ENTIDADE"],
        "uf": df["SG_UF"],
        "rede": df["TP_DEPENDENCIA"].map(REDES),
    })
    for c in MATRICULAS:
        out[c.lower()] = df[c].to_numpy()
    out["ano_ref"] = ano

    assert out["co_entidade"].is_unique
    assert out["rede"].notna().all()
    assert out["cod_ibge_7"].str.fullmatch(r"\d{7}").all()
    return out.reset_index(drop=True)


def agregar_municipio(escolas: pd.DataFrame) -> pd.DataFrame:
    mat = [c.lower() for c in MATRICULAS]
    agg = (
        escolas.groupby(["cod_ibge_7", "rede"], as_index=False)
        .agg(n_escolas=("co_entidade", "size"), **{c: (c, "sum") for c in mat})
    )
    agg["ano_ref"] = escolas["ano_ref"].iloc[0]
    return agg


def descricoes_inep(ano: int) -> dict[str, str]:
    """Descrição oficial de cada variável, lida do dicionário do INEP dentro do zip."""
    zpath = RAW / "inep" / f"microdados_censo_escolar_{ano}.zip"
    with zipfile.ZipFile(zpath) as zf:
        (membro,) = [n for n in zf.namelist()
                     if n.endswith(".xlsx") and "dicion" in n.lower() and "/~$" not in n]
        d = pd.read_excel(io.BytesIO(zf.read(membro)), sheet_name="microdados_unidade_coleta",
                          header=None, dtype=str)
    d = d.iloc[:, [1, 2]].dropna()
    return dict(zip(d.iloc[:, 0].str.strip(), d.iloc[:, 1].str.split().str.join(" ")))


def dicionarios(ano: int) -> tuple[dict[str, Col], dict[str, Col]]:
    desc = descricoes_inep(ano)
    fonte = f"INEP — Censo Escolar {ano}, microdados (microdados_ed_basica_{ano}.csv)"
    mat = {c.lower(): Col(desc[c] + " (escolas em atividade; nulo tratado como 0)",
                          "matrículas", "publicado", fonte) for c in MATRICULAS}
    escolas = {
        "cod_ibge_7": COMUNS["cod_ibge_7"],
        "co_entidade": Col(desc["CO_ENTIDADE"] + " (código INEP, 8 dígitos)", "código", "chave", fonte),
        "no_entidade": Col(desc["NO_ENTIDADE"], "texto", "referencia", fonte),
        "uf": COMUNS["uf"],
        "rede": Col("Dependência administrativa (TP_DEPENDENCIA): federal, estadual, municipal, privada",
                    "categoria", "publicado", fonte),
        **mat,
        "ano_ref": Col("Ano do Censo Escolar", "ano", "referencia", fonte),
    }
    municipio = {
        "cod_ibge_7": COMUNS["cod_ibge_7"],
        "rede": escolas["rede"],
        "n_escolas": Col("Número de escolas em atividade da rede no município", "escolas",
                         "calculado", fonte),
        **{c: Col(m.descricao.replace("(escolas", "— soma das escolas da rede no município (escolas"),
                  m.unidade, "calculado", m.fonte) for c, m in mat.items()},
        "ano_ref": escolas["ano_ref"],
    }
    return escolas, municipio


def run(ano: int = ANO_PADRAO) -> tuple[pd.DataFrame, pd.DataFrame]:
    escolas = ler_escolas(ano)
    mun = agregar_municipio(escolas)
    INTERIM.mkdir(parents=True, exist_ok=True)
    dic_esc, dic_mun = dicionarios(ano)
    escolas.to_parquet(INTERIM / "ref_escolas.parquet", index=False)
    dicionario.salvar(escolas, dic_esc, INTERIM / "ref_escolas.parquet")
    mun.to_parquet(INTERIM / "ref_matriculas_municipio.parquet", index=False)
    dicionario.salvar(mun, dic_mun, INTERIM / "ref_matriculas_municipio.parquet")
    return escolas, mun


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ano", type=int, default=ANO_PADRAO)
    a = p.parse_args()
    esc, mun = run(a.ano)
    print(f"escolas em atividade: {len(esc):,} | municípios: {esc.cod_ibge_7.nunique():,}")
    print(mun.groupby("rede")[["n_escolas", "qt_mat_bas", "qt_mat_med"]].sum())
