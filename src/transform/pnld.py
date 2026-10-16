"""Fase 2a/3 — PNLD 2025 por município: ESTIMATIVA por rateio dos totais da UF.

O FNDE só publica o PNLD por UF. Cada etapa da UF (alunos e valor) é rateada entre os
municípios pela participação nas matrículas públicas (federal + estadual + municipal)
da etapa correspondente no Censo Escolar. Todas as colunas de valor/aluno são estimativa.

Limitação conhecida: o rateio supõe que todas as redes públicas da UF aderem ao PNLD
na etapa. Onde isso não vale (ex.: MT, anos finais e ensino médio, cobertura 16% e 6%),
o valor é atribuído a escolas que podem não receber livros → flag_pnld_cobertura_baixa_uf.

Saída: data/interim/pnld_municipio_2025.parquet + data/processed/pnld_municipio_2025.csv
"""
from __future__ import annotations

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.manifest import INTERIM, PROCESSED

ANO = 2025
REDES_PUBLICAS = ["federal", "estadual", "municipal"]
# etapa PNLD -> matrículas do Censo usadas como base do rateio
BASE = {
    "ei_literario": "qt_mat_inf",
    "ei_didatico": "qt_mat_inf_pre",
    "ai_didatico": "qt_mat_fund_ai",
    "ai_praticas": "qt_mat_fund_ai",
    "af": "qt_mat_fund_af",
    "af_braille": "qt_mat_fund_af",
    "em": "qt_mat_med",
}
# Alunos afetados: um objeto por etapa (o de maior alcance), para não contar o mesmo aluno duas vezes.
# Mesma regra do TOTAL de alunos publicado pelo FNDE (checada em src/ingest/pnld.py).
ALUNOS_ETAPA = {"ei": "ei_literario", "ai": "ai_didatico", "af": "af", "em": "em"}
LIMITE_COBERTURA = 0.7


def run() -> pd.DataFrame:
    pnld = pd.read_parquet(INTERIM / f"pnld_uf_{ANO}.parquet")
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7", "municipio", "uf"]]
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(m.ano_ref.iloc[0])
    bases = sorted(set(BASE.values()))
    mat = m[m.rede.isin(REDES_PUBLICAS)].groupby("cod_ibge_7")[bases].sum()

    out = ref.merge(mat, on="cod_ibge_7", how="left")
    out[bases] = out[bases].fillna(0)
    tot_uf = out.groupby("uf")[bases].transform("sum")

    for etapa, base in BASE.items():
        uf = pnld[pnld.etapa_pnld == etapa].set_index("uf")
        share = out[base] / tot_uf[base].where(tot_uf[base] > 0)
        out[f"vl_pnld_{etapa}_est"] = share * out.uf.map(uf.vl_pnld)
        out[f"alunos_pnld_{etapa}_est"] = share * out.uf.map(uf.qtd_alunos)
        cob = uf.qtd_alunos / out.groupby("uf")[base].sum()
        out[f"cobertura_pnld_uf_{etapa}"] = out.uf.map(cob)

    vl = [f"vl_pnld_{e}_est" for e in BASE]
    out["vl_pnld_total_est"] = out[vl].sum(axis=1, min_count=1)
    out["afetados_pnld"] = sum(out[f"alunos_pnld_{e}_est"].fillna(0) for e in ALUNOS_ETAPA.values()).round()
    out["vl_pnld_por_aluno_est"] = out.vl_pnld_total_est / out.afetados_pnld.where(out.afetados_pnld > 0)
    principais = [f"cobertura_pnld_uf_{e}" for e in ALUNOS_ETAPA.values()]
    out["flag_pnld_cobertura_baixa_uf"] = (out[principais] < LIMITE_COBERTURA).any(axis=1)

    # Arredonda alunos rateados para inteiro (são contagens estimadas).
    for e in BASE:
        out[f"alunos_pnld_{e}_est"] = out[f"alunos_pnld_{e}_est"].round()
    out = out.drop(columns=bases)
    out["ano_ref"] = ANO
    out["ano_ref_censo"] = ano_censo

    # Reconciliação: o rateio devolve o valor de cada UF × etapa.
    for etapa in BASE:
        uf = pnld[pnld.etapa_pnld == etapa].set_index("uf").vl_pnld
        rat = out.groupby("uf")[f"vl_pnld_{etapa}_est"].sum()
        assert (rat - uf.reindex(rat.index)).abs().max() < 1, etapa
    assert out.cod_ibge_7.is_unique and len(out) == len(ref)

    out.to_parquet(INTERIM / f"pnld_municipio_{ANO}.parquet", index=False)
    dicionario.salvar(out, dicionario_(), INTERIM / f"pnld_municipio_{ANO}.parquet")
    _salvar_csv(out)
    return out


def _salvar_csv(out: pd.DataFrame) -> None:
    csv = out.copy()
    vl = [c for c in csv if c.startswith("vl_")]
    csv[vl] = csv[vl].round(2)
    cob = [c for c in csv if c.startswith("cobertura_")]
    csv[cob] = csv[cob].round(4)
    al = [c for c in csv if c.startswith(("alunos_", "afetados_"))]
    csv[al] = csv[al].astype("Int64")
    destino = PROCESSED / f"pnld_municipio_{ANO}.csv"
    csv.to_csv(destino, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    dicionario.salvar(csv, dicionario_(), destino)


def dicionario_() -> dict[str, Col]:
    fp = "FNDE — PNLD 2025 por UF (pnld_uf_2025)"
    fc = "INEP — Censo Escolar (ref_matriculas_municipio)"
    nomes = {
        "ei_literario": "Educação Infantil – literário", "ei_didatico": "Educação Infantil – didático",
        "ai_didatico": "Anos Iniciais – didático (objeto 1)", "ai_praticas": "Anos Iniciais – práticas (objeto 2)",
        "af": "Anos Finais", "af_braille": "Anos Finais – Braille", "em": "Ensino Médio",
    }
    rateio = "ESTIMATIVA: total da UF × participação do município nas matrículas públicas ({base}) da UF"
    d = {"cod_ibge_7": COMUNS["cod_ibge_7"], "municipio": COMUNS["municipio"], "uf": COMUNS["uf"]}
    for e, base in BASE.items():
        d[f"vl_pnld_{e}_est"] = Col(f"Valor do PNLD 2025 — {nomes[e]}. " + rateio.format(base=base),
                                    "R$", "estimativa", f"{fp}; {fc}")
        d[f"alunos_pnld_{e}_est"] = Col(f"Alunos beneficiados — {nomes[e]}. " + rateio.format(base=base),
                                        "alunos", "estimativa", f"{fp}; {fc}")
        d[f"cobertura_pnld_uf_{e}"] = Col(f"Alunos do PNLD na UF ÷ matrículas públicas da UF ({base}) — "
                                          f"{nomes[e]}. Muito abaixo de 1 indica rede que não adere",
                                          "razão", "calculado", f"{fp}; {fc}")
    d.update({
        "vl_pnld_total_est": Col("Soma dos valores estimados de todas as etapas/objetos", "R$",
                                 "estimativa", f"{fp}; {fc}"),
        "afetados_pnld": Col("Alunos afetados por corte do PNLD: soma, por etapa, do objeto de maior alcance "
                             "(EI literário + AI didático + AF + EM), sem somar objetos da mesma etapa — mesma regra "
                             "do TOTAL de alunos publicado pelo FNDE",
                             "alunos", "estimativa", f"{fp}; {fc}"),
        "vl_pnld_por_aluno_est": Col("vl_pnld_total_est ÷ afetados_pnld", "R$/aluno", "estimativa",
                                     f"{fp}; {fc}"),
        "flag_pnld_cobertura_baixa_uf": Col(f"Verdadeiro se alguma etapa principal da UF tem cobertura < "
                                            f"{LIMITE_COBERTURA}: o rateio pode atribuir livros a redes que "
                                            "não aderem (ex.: MT)", "booleano", "calculado", f"{fp}; {fc}"),
        "ano_ref": Col("Ano do PNLD", "ano", "referencia", fp),
        "ano_ref_censo": COMUNS["ano_ref_censo"],
    })
    return d


if __name__ == "__main__":
    o = run()
    print(f"municípios: {len(o):,} | valor estimado: R$ {o.vl_pnld_total_est.sum():,.2f}")
    print(f"afetados: {o.afetados_pnld.sum():,.0f} | por aluno (mediana): R$ {o.vl_pnld_por_aluno_est.median():,.2f}")
    print("UFs com cobertura baixa:", sorted(o[o.flag_pnld_cobertura_baixa_uf].uf.unique()),
          "| municípios:", int(o.flag_pnld_cobertura_baixa_uf.sum()))
    cob = o.groupby("uf")[[f"cobertura_pnld_uf_{e}" for e in ALUNOS_ETAPA.values()]].first().round(2)
    print(cob[(cob < 0.85).any(axis=1)])
