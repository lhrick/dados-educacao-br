"""Fase 2b/3 — Fomento ETI 2025 por município (rede municipal + rede estadual estimada).

Rede municipal: valor e matrículas fomentadas publicados por rede (Portarias MEC 605 e 823/2025).
Rede estadual: valor e matrículas do estado rateados pela participação do município nas
matrículas em tempo integral da rede estadual da UF (Censo: inf + fund + médio integral).
É ESTIMATIVA — colunas com sufixo `_est`.

Atenção: o fomento ETI 2025 saiu da complementação da União ao Fundeb 2025. Não somar com
valores do Fundeb do mesmo exercício.

Saída: data/interim/eti_municipio_2025.parquet + data/processed/eti_municipio_2025.csv
"""
from __future__ import annotations

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.ingest.eti import DICIONARIO as DIC_REDES
from src.manifest import INTERIM, PROCESSED

ANO = 2025
INTEGRAL = ["qt_mat_inf_int", "qt_mat_fund_int", "qt_mat_med_int"]


def run() -> pd.DataFrame:
    redes = pd.read_parquet(INTERIM / f"eti_redes_{ANO}.parquet")
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7", "municipio", "uf"]]
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(m.ano_ref.iloc[0])
    m["mat_integral"] = m[INTEGRAL].sum(axis=1)
    integ = m[m.rede.isin(["municipal", "estadual"])].pivot_table(
        index="cod_ibge_7", columns="rede", values="mat_integral", aggfunc="sum", fill_value=0)
    integ = integ.rename(columns={"municipal": "mat_integral_censo_mun", "estadual": "mat_integral_censo_est"})

    out = ref.merge(integ.reset_index(), on="cod_ibge_7", how="left")
    out[["mat_integral_censo_mun", "mat_integral_censo_est"]] = (
        out[["mat_integral_censo_mun", "mat_integral_censo_est"]].fillna(0).astype("int64"))

    mun = redes[redes.rede == "municipal"].set_index("cod_ibge")
    out["vl_fomento_eti_mun"] = out.cod_ibge_7.map(mun.vl_fomento_eti)
    out["qtd_matriculas_eti_mun"] = out.cod_ibge_7.map(mun.qtd_matriculas_eti).astype("Int64")
    out["registrou_politica_eti_mun"] = out.cod_ibge_7.map(mun.registrou_politica_eti).astype("boolean")

    est = redes[redes.rede == "estadual"].set_index("uf")
    tot = out.groupby("uf").mat_integral_censo_est.transform("sum")
    out["share_integral_estadual_uf"] = out.mat_integral_censo_est / tot.where(tot > 0)
    out["vl_fomento_eti_est"] = out.share_integral_estadual_uf * out.uf.map(est.vl_fomento_eti)
    out["qtd_matriculas_eti_est"] = (out.share_integral_estadual_uf * out.uf.map(est.qtd_matriculas_eti)).round()

    out["afetados_eti"] = (out.qtd_matriculas_eti_mun.fillna(0).astype("float")
                           + out.qtd_matriculas_eti_est.fillna(0)).round().astype("int64")
    out["vl_fomento_eti_total"] = out.vl_fomento_eti_mun.fillna(0) + out.vl_fomento_eti_est.fillna(0)
    out["ano_ref"] = ANO
    out["ano_ref_censo"] = ano_censo

    rat = out.groupby("uf").vl_fomento_eti_est.sum()
    assert (rat - est.vl_fomento_eti.reindex(rat.index)).abs().max() < 1
    total = out.vl_fomento_eti_mun.sum() + out.vl_fomento_eti_est.sum()
    assert abs(total - redes.vl_fomento_eti.sum()) < 10, total
    assert out.cod_ibge_7.is_unique and len(out) == len(ref)

    out.to_parquet(INTERIM / f"eti_municipio_{ANO}.parquet", index=False)
    dicionario.salvar(out, dicionario_(), INTERIM / f"eti_municipio_{ANO}.parquet")
    csv = out.copy()
    vl = [c for c in csv if c.startswith("vl_")]
    csv[vl] = csv[vl].round(2)
    csv["share_integral_estadual_uf"] = csv.share_integral_estadual_uf.round(6)
    csv["qtd_matriculas_eti_est"] = csv.qtd_matriculas_eti_est.astype("Int64")
    destino = PROCESSED / f"eti_municipio_{ANO}.csv"
    csv.to_csv(destino, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    dicionario.salvar(csv, dicionario_(), destino)
    return out


def dicionario_() -> dict[str, Col]:
    fr = "eti_redes_2025 (Portarias MEC 605 e 823/2025, DOU)"
    fc = "INEP — Censo Escolar (ref_matriculas_municipio)"
    rateio = ("ESTIMATIVA: valor do governo estadual × share_integral_estadual_uf "
              "(matrículas em tempo integral da rede estadual no município ÷ na UF)")
    return {
        "cod_ibge_7": COMUNS["cod_ibge_7"], "municipio": COMUNS["municipio"], "uf": COMUNS["uf"],
        "mat_integral_censo_mun": Col("Matrículas em tempo integral da rede municipal (inf + fund + médio)",
                                      "matrículas", "calculado", fc),
        "mat_integral_censo_est": Col("Matrículas em tempo integral da rede estadual no município "
                                      "(inf + fund + médio)", "matrículas", "calculado", fc),
        "vl_fomento_eti_mun": Col(DIC_REDES["vl_fomento_eti"].descricao + " — rede municipal "
                                  "(vazio = município fora do anexo)", "R$", "publicado", fr),
        "qtd_matriculas_eti_mun": Col(DIC_REDES["qtd_matriculas_eti"].descricao + " — rede municipal",
                                      "matrículas", "publicado", fr),
        "registrou_politica_eti_mun": Col(DIC_REDES["registrou_politica_eti"].descricao + " — rede municipal",
                                          "booleano", "publicado", fr),
        "share_integral_estadual_uf": Col("Matrículas integrais da rede estadual no município ÷ na UF "
                                          "(base do rateio)", "proporção (0–1)", "calculado", fc),
        "vl_fomento_eti_est": Col("Fomento ETI 2025 da rede estadual atribuído ao município. " + rateio,
                                  "R$", "estimativa", f"{fr}; {fc}"),
        "qtd_matriculas_eti_est": Col("Matrículas fomentadas da rede estadual atribuídas ao município. " + rateio,
                                      "matrículas", "estimativa", f"{fr}; {fc}"),
        "afetados_eti": Col("Matrículas em tempo integral fomentadas no município: rede municipal "
                            "(publicado) + rede estadual (rateio)", "matrículas", "estimativa", f"{fr}; {fc}"),
        "vl_fomento_eti_total": Col("vl_fomento_eti_mun + vl_fomento_eti_est. Sai da complementação da União "
                                    "ao Fundeb 2025 — não somar com Fundeb do mesmo ano", "R$", "estimativa",
                                    f"{fr}; {fc}"),
        "ano_ref": Col("Ciclo do fomento ETI", "ano", "referencia", fr),
        "ano_ref_censo": COMUNS["ano_ref_censo"],
    }


if __name__ == "__main__":
    o = run()
    print(f"municípios: {len(o):,} | com fomento municipal > 0: {(o.vl_fomento_eti_mun > 0).sum():,}")
    print(f"fomento municipal R$ {o.vl_fomento_eti_mun.sum()/1e9:.3f} bi | estadual rateado "
          f"R$ {o.vl_fomento_eti_est.sum()/1e9:.3f} bi | afetados {o.afetados_eti.sum():,}")
