"""Fase 2b/3 — Fundeb 2025 por município, a partir dos REPASSES EFETIVOS (Tesouro).

Rede municipal: soma dos repasses do ano ao município (publicado).
Rede estadual: repasses ao governo estadual rateados pelas matrículas da rede estadual
no município (Censo) — ESTIMATIVA, sufixo `_est`.

Receita do ano (`vl_receita_*`) = contribuição + complementação da União (VAAF+VAAT+VAAR).
Ficam FORA do total e em colunas próprias:
- FTI (fomento ao tempo integral) = mesmo dinheiro da tabela ETI → não somar com ETI;
- ajustes de exercícios anteriores pagos no ano.
Base de caixa: jan/2025 inclui a 13ª parcela da complementação de 2024; a de 2025 cai em jan/2026.

Saída: data/interim/fundeb_municipio_<ano>.parquet + data/processed/fundeb_municipio_<ano>.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.manifest import INTERIM, PROCESSED

COMP = ["contribuicao", "compl_vaaf", "compl_vaat", "compl_vaar", "fti", "ajuste"]


def _pivot(rep: pd.DataFrame, tipo: str, idx: str) -> pd.DataFrame:
    p = (rep[rep.tipo_ente == tipo].pivot_table(index=idx, columns="componente", values="valor",
                                                 aggfunc="sum", fill_value=0.0)
         .reindex(columns=COMP, fill_value=0.0))
    p["compl_uniao"] = p[["compl_vaaf", "compl_vaat", "compl_vaar"]].sum(axis=1)
    p["receita"] = p.contribuicao + p.compl_uniao
    return p


def run(ano: int = 2025) -> pd.DataFrame:
    rep = pd.read_parquet(INTERIM / f"fundeb_repasses_{ano}.parquet")
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7", "municipio", "uf"]]
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(m.ano_ref.iloc[0])
    mat = m[m.rede.isin(["municipal", "estadual"])].pivot_table(
        index="cod_ibge_7", columns="rede", values="qt_mat_bas", aggfunc="sum", fill_value=0)
    mat = mat.rename(columns={"municipal": "mat_rede_municipal", "estadual": "mat_rede_estadual"})

    out = ref.merge(mat.reset_index(), on="cod_ibge_7", how="left")
    out[["mat_rede_municipal", "mat_rede_estadual"]] = (
        out[["mat_rede_municipal", "mat_rede_estadual"]].fillna(0).astype("int64"))

    mun = _pivot(rep, "municipio", "cod_ibge")
    assert mun.index.isin(ref.cod_ibge_7).all(), mun.index[~mun.index.isin(ref.cod_ibge_7)]
    for c in mun.columns:
        out[f"vl_{c}_mun"] = out.cod_ibge_7.map(mun[c])

    est = _pivot(rep, "estado", "uf")
    tot = out.groupby("uf").mat_rede_estadual.transform("sum")
    out["share_mat_estadual_uf"] = out.mat_rede_estadual / tot.where(tot > 0)
    for c in est.columns:
        out[f"vl_{c}_est"] = out.share_mat_estadual_uf * out.uf.map(est[c])

    out["vl_fundeb_por_aluno_mun"] = out.vl_receita_mun / out.mat_rede_municipal.where(out.mat_rede_municipal > 0)
    out["vl_fundeb_por_aluno_est"] = out.uf.map(
        est.receita / out.groupby("uf").mat_rede_estadual.sum().where(lambda s: s > 0))
    out["pct_uniao_mun"] = out.vl_compl_uniao_mun / out.vl_receita_mun.where(out.vl_receita_mun > 0)
    out["pct_uniao_est"] = out.uf.map(est.compl_uniao / est.receita)
    for c in ["vaaf", "vaat", "vaar"]:
        out[f"recebe_{c}_mun"] = (out[f"vl_compl_{c}_mun"].fillna(0) > 0)
        out[f"recebe_{c}_est"] = out.uf.map(est[f"compl_{c}"] > 0).astype("boolean")

    recebe_mun = out[["recebe_vaaf_mun", "recebe_vaat_mun", "recebe_vaar_mun"]].any(axis=1)
    recebe_est = out[["recebe_vaaf_est", "recebe_vaat_est", "recebe_vaar_est"]].fillna(False).any(axis=1)
    out["afetados_fundeb_complementacao"] = (out.mat_rede_municipal.where(recebe_mun, 0)
                                             + out.mat_rede_estadual.where(recebe_est, 0))
    out["perda_fundeb_sem_uniao"] = out.vl_compl_uniao_mun.fillna(0) + out.vl_compl_uniao_est.fillna(0)
    out["risco_perda_vaar"] = out.recebe_vaar_mun
    out["vl_fundeb_total_mun_mais_est"] = out.vl_receita_mun.fillna(0) + out.vl_receita_est.fillna(0)
    out["ano_ref"] = ano
    out["ano_ref_censo"] = ano_censo
    out["fonte_valores"] = f"Repasses efetivos {ano} — Tesouro Nacional, Transferências Constitucionais"

    # Reconciliação: municipal + estadual rateado = tudo o que a API registrou no ano.
    for c in ["receita", "fti", "ajuste"]:
        total = out[f"vl_{c}_mun"].sum() + out[f"vl_{c}_est"].sum()
        assert abs(total - mun[c].sum() - est[c].sum()) < 10, c
    assert out.cod_ibge_7.is_unique and len(out) == len(ref)

    out.to_parquet(INTERIM / f"fundeb_municipio_{ano}.parquet", index=False)
    dicionario.salvar(out, dicionario_(ano), INTERIM / f"fundeb_municipio_{ano}.parquet")
    csv = out.copy()
    vl = [c for c in csv if c.startswith(("vl_", "perda_"))]
    csv[vl] = csv[vl].round(2)
    for c in ["share_mat_estadual_uf", "pct_uniao_mun", "pct_uniao_est"]:
        csv[c] = csv[c].round(6)
    destino = PROCESSED / f"fundeb_municipio_{ano}.csv"
    csv.to_csv(destino, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    dicionario.salvar(csv, dicionario_(ano), destino)
    return out


def dicionario_(ano: int) -> dict[str, Col]:
    ft = f"fundeb_repasses_{ano} (Tesouro Nacional — Transferências Constitucionais)"
    fc = "INEP — Censo Escolar (ref_matriculas_municipio)"
    rateio = ("ESTIMATIVA: repasse ao governo estadual × share_mat_estadual_uf "
              "(rateio pelas matrículas da rede estadual no município)")
    desc = {
        "contribuicao": "Contribuição de estados e municípios (FPM, FPE, ICMS, IPVA, ITCMD, ITR, IPI-Exp) "
                        f"repassada em {ano}",
        "compl_vaaf": f"Complementação da União VAAF repassada em {ano}",
        "compl_vaat": f"Complementação da União VAAT repassada em {ano}",
        "compl_vaar": f"Complementação da União VAAR repassada em {ano}",
        "fti": f"Fomento ao tempo integral (FTI = ETI) repassado em {ano}. Mesmo recurso da tabela ETI — "
               "NÃO somar com ETI; fora de vl_receita",
        "ajuste": f"Ajustes de exercícios anteriores pagos em {ano} (pode ser negativo); fora de vl_receita",
        "compl_uniao": "Complementação da União total (VAAF + VAAT + VAAR)",
        "receita": f"Receita Fundeb do ano = contribuição + complementação da União (base de caixa {ano}: "
                   "jan inclui 13ª parcela do ano anterior)",
    }
    d = {
        "cod_ibge_7": COMUNS["cod_ibge_7"], "municipio": COMUNS["municipio"], "uf": COMUNS["uf"],
        "mat_rede_estadual": Col("Matrículas da educação básica da rede estadual no município (qt_mat_bas)",
                                 "matrículas", "publicado", fc),
        "mat_rede_municipal": Col("Matrículas da educação básica da rede municipal (qt_mat_bas)",
                                  "matrículas", "publicado", fc),
        "share_mat_estadual_uf": Col("Matrículas da rede estadual no município ÷ na UF (base do rateio)",
                                     "proporção (0–1)", "calculado", fc),
        "vl_fundeb_por_aluno_mun": Col("vl_receita_mun ÷ mat_rede_municipal (matrículas do Censo sem "
                                       "ponderação; o Fundeb usa matrículas ponderadas)", "R$/aluno",
                                       "estimativa", f"{ft}; {fc}"),
        "vl_fundeb_por_aluno_est": Col("Receita do governo estadual ÷ matrículas da rede estadual na UF "
                                       "(mesmo valor para a UF; idem ponderação)", "R$/aluno", "estimativa",
                                       f"{ft}; {fc}"),
        "pct_uniao_mun": Col("vl_compl_uniao_mun ÷ vl_receita_mun", "proporção (0–1)", "calculado", ft),
        "pct_uniao_est": Col("Complementação da União ÷ receita do governo estadual", "proporção (0–1)",
                             "calculado", ft),
        "afetados_fundeb_complementacao": Col("Matrículas das redes (municipal e/ou estadual no município) que "
                                              "receberam complementação da União no ano", "matrículas",
                                              "calculado", f"{ft}; {fc}"),
        "perda_fundeb_sem_uniao": Col("Complementação da União que deixaria de chegar: rede municipal "
                                      "(publicado) + estadual (rateio)", "R$", "estimativa", ft),
        "risco_perda_vaar": Col("Verdadeiro se a rede municipal recebeu VAAR no ano (depende de "
                                "condicionalidades)", "booleano", "calculado", ft),
        "vl_fundeb_total_mun_mais_est": Col("vl_receita_mun + vl_receita_est (inclui rateio)", "R$",
                                            "estimativa", ft),
        "ano_ref": Col("Ano dos repasses (base de caixa)", "ano", "referencia", ft),
        "ano_ref_censo": COMUNS["ano_ref_censo"],
        "fonte_valores": Col("Origem dos valores", "texto", "referencia", ft),
    }
    for c, txt in desc.items():
        d[f"vl_{c}_mun"] = Col(f"{txt} — rede municipal", "R$", "publicado" if c not in ("compl_uniao", "receita")
                               else "calculado", ft)
        d[f"vl_{c}_est"] = Col(f"{txt} — rede estadual no município. {rateio}", "R$", "estimativa", ft)
    for c in ["vaaf", "vaat", "vaar"]:
        d[f"recebe_{c}_mun"] = Col(f"Verdadeiro se a rede municipal recebeu complementação {c.upper()} no ano",
                                   "booleano", "calculado", ft)
        d[f"recebe_{c}_est"] = Col(f"Verdadeiro se o governo estadual recebeu complementação {c.upper()} no ano",
                                   "booleano", "calculado", ft)
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2025)
    o = run(ap.parse_args().ano)
    print(f"municípios com repasse: {o.vl_receita_mun.notna().sum():,}")
    for c in ["receita", "contribuicao", "compl_uniao", "fti", "ajuste"]:
        print(f"  {c:13s} mun R$ {o[f'vl_{c}_mun'].sum()/1e9:8.3f} bi | est R$ {o[f'vl_{c}_est'].sum()/1e9:8.3f} bi")
    print("por aluno municipal (mediana):", round(o.vl_fundeb_por_aluno_mun.median(), 2))
    print("recebem VAAF/VAAT/VAAR (mun):", o[["recebe_vaaf_mun", "recebe_vaat_mun", "recebe_vaar_mun"]].sum().to_dict())
