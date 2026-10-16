"""Fase 2b/3 — Fundeb 2026 por município (rede municipal + rede estadual estimada).

Rede municipal: valores publicados por ente (Anexo I da Portaria Interministerial nº 6/2026).

Rede estadual: o Fundeb do governo estadual é um valor único por UF. Para atribuí-lo às
cidades, rateamos pela participação do município nas matrículas da rede estadual da UF
(Censo Escolar). É ESTIMATIVA — colunas com sufixo `_est`.

Valor por aluno: receita da rede ÷ matrículas da educação básica da rede no Censo
(`qt_mat_bas`). Aproximação provisória: o Fundeb 2026 distribui por matrículas
ponderadas do Censo 2025, que ainda não temos por ente (pendência em docs/fontes.md).

Saída: data/interim/fundeb_municipio_2026.parquet + data/processed/fundeb_municipio_2026.csv
"""
from __future__ import annotations

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.ingest.fundeb import DICIONARIO as DIC_ENTES
from src.manifest import INTERIM, PROCESSED

ANO = 2026
VL = ["vl_contribuicao_ente", "vl_compl_vaaf", "vl_compl_vaat", "vl_compl_vaar",
      "vl_compl_uniao", "vl_receita_total"]


def _matriculas() -> tuple[pd.DataFrame, int]:
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(m.ano_ref.iloc[0])
    m = m[m.rede.isin(["municipal", "estadual"])].pivot_table(
        index="cod_ibge_7", columns="rede", values="qt_mat_bas", aggfunc="sum", fill_value=0)
    m = m.rename(columns={"municipal": "mat_rede_municipal", "estadual": "mat_rede_estadual"})
    return m.reset_index(), ano_censo


def run() -> pd.DataFrame:
    entes = pd.read_parquet(INTERIM / f"fundeb_entes_{ANO}.parquet")
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7", "municipio", "uf"]]
    mat, ano_censo = _matriculas()
    out = ref.merge(mat, on="cod_ibge_7", how="left")
    out[["mat_rede_municipal", "mat_rede_estadual"]] = (
        out[["mat_rede_municipal", "mat_rede_estadual"]].fillna(0).astype("int64"))

    # --- rede municipal (valores publicados)
    mun = entes[entes.tipo_ente == "municipio"].set_index("cod_ibge")
    for c in VL:
        out[f"{c}_mun"] = out.cod_ibge_7.map(mun[c])
    for c in ["recebe_vaaf", "recebe_vaat", "recebe_vaar"]:
        out[f"{c}_mun"] = out.cod_ibge_7.map(mun[c]).astype("boolean")
    out["vaat_com_compl_mun"] = out.cod_ibge_7.map(mun.vaat_com_compl)
    out["sem_vaat_calculado_mun"] = out.cod_ibge_7.isin(mun.index) & out.vaat_com_compl_mun.isna()

    # --- rede estadual (rateio por matrículas estaduais do Censo) — ESTIMATIVA
    est = entes[entes.tipo_ente == "estado"].set_index("uf")
    total_uf = out.groupby("uf").mat_rede_estadual.transform("sum")
    out["share_mat_estadual_uf"] = out.mat_rede_estadual / total_uf.where(total_uf > 0)
    for c in VL:
        out[f"{c}_est"] = out.share_mat_estadual_uf * out.uf.map(est[c])
    for c in ["recebe_vaaf", "recebe_vaat", "recebe_vaar"]:
        out[f"{c}_est"] = out.uf.map(est[c]).astype("boolean")
    out["sem_vaat_calculado_est"] = out.uf.map(est.vaat_com_compl.isna())

    # --- valor por aluno (aproximação: matrículas do Censo, sem ponderação)
    out["vl_fundeb_por_aluno_mun"] = (
        out.vl_receita_total_mun / out.mat_rede_municipal.where(out.mat_rede_municipal > 0))
    out["vl_fundeb_por_aluno_est"] = out.uf.map(
        est.vl_receita_total / out.groupby("uf").mat_rede_estadual.sum().where(lambda s: s > 0))
    out["pct_uniao_mun"] = out.vl_compl_uniao_mun / out.vl_receita_total_mun.where(out.vl_receita_total_mun > 0)
    out["pct_uniao_est"] = out.uf.map(est.pct_uniao)

    # --- Fase 3: cenários (Fundeb não tem "corte total"; risco = complementação da União)
    recebe_mun = out[["recebe_vaaf_mun", "recebe_vaat_mun", "recebe_vaar_mun"]].fillna(False).any(axis=1)
    recebe_est = out[["recebe_vaaf_est", "recebe_vaat_est", "recebe_vaar_est"]].fillna(False).any(axis=1)
    out["afetados_fundeb_complementacao"] = (
        out.mat_rede_municipal.where(recebe_mun, 0) + out.mat_rede_estadual.where(recebe_est, 0))
    out["perda_fundeb_sem_uniao"] = (
        out.vl_compl_uniao_mun.fillna(0) + out.vl_compl_uniao_est.fillna(0))
    out["risco_perda_vaar"] = out.recebe_vaar_mun.fillna(False)
    out["vl_fundeb_total_mun_mais_est"] = (
        out.vl_receita_total_mun.fillna(0) + out.vl_receita_total_est.fillna(0))

    out["ano_ref"] = ANO
    out["ano_ref_censo"] = ano_censo
    out["fonte_ato"] = entes.fonte_ato.iloc[0]

    # Reconciliação: rateio devolve exatamente o total estadual de cada UF.
    rec = out.groupby("uf").vl_receita_total_est.sum()
    assert (rec - est.vl_receita_total.reindex(rec.index)).abs().max() < 1.0
    assert out.cod_ibge_7.is_unique and len(out) == len(ref)

    out.to_parquet(INTERIM / f"fundeb_municipio_{ANO}.parquet", index=False)
    dicionario.salvar(out, dicionario_(), INTERIM / f"fundeb_municipio_{ANO}.parquet")
    _salvar_csv(out)
    return out


def _salvar_csv(out: pd.DataFrame) -> None:
    csv = out.copy()
    vl = [c for c in csv if c.startswith(("vl_", "perda_"))]
    csv[vl] = csv[vl].round(2)
    for c in ["share_mat_estadual_uf", "pct_uniao_mun", "pct_uniao_est"]:
        csv[c] = csv[c].round(6)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / f"fundeb_municipio_{ANO}.csv"
    csv.to_csv(destino, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    dicionario.salvar(csv, dicionario_(), destino)


def dicionario_() -> dict[str, Col]:
    fe = "FNDE — fundeb_entes_2026 (Portaria Interministerial MEC/MF nº 6/2026)"
    fc = "INEP — Censo Escolar (ref_matriculas_municipio)"
    rateio = ("ESTIMATIVA: valor do governo estadual × share_mat_estadual_uf "
              "(rateio pelas matrículas da rede estadual no município)")
    d = {
        "cod_ibge_7": COMUNS["cod_ibge_7"], "municipio": COMUNS["municipio"], "uf": COMUNS["uf"],
        "mat_rede_estadual": Col("Matrículas da educação básica da rede estadual no município (qt_mat_bas)",
                                 "matrículas", "publicado", fc),
        "mat_rede_municipal": Col("Matrículas da educação básica da rede municipal (qt_mat_bas)",
                                  "matrículas", "publicado", fc),
        "vaat_com_compl_mun": Col(DIC_ENTES["vaat_com_compl"].descricao + " — rede municipal",
                                  "R$/aluno", "publicado", fe),
        "sem_vaat_calculado_mun": Col("Verdadeiro se o município está no Fundeb mas sem VAAT no Anexo III. "
                                      "Provável inabilitação ao VAAT por dados de 2024 não enviados ao "
                                      "SIOPE/SICONFI: 22 dos 23 estão na lista preliminar do FNDE (19/05/2025); "
                                      "o outro é Boa Esperança do Norte, município novo. Lista definitiva não "
                                      "localizada", "booleano", "calculado", fe),
        "sem_vaat_calculado_est": Col("Verdadeiro se o governo estadual da UF está sem VAAT no Anexo III "
                                      "(em 2026: só MG; provável inabilitação, idem)", "booleano",
                                      "calculado", fe),
        "share_mat_estadual_uf": Col("Matrículas da rede estadual no município ÷ matrículas da rede "
                                     "estadual na UF (base do rateio)", "proporção (0–1)", "calculado", fc),
        "vl_fundeb_por_aluno_mun": Col("vl_receita_total_mun ÷ mat_rede_municipal. PROVISÓRIO: Censo sem "
                                       "ponderação; o FNDE usa matrículas ponderadas do Censo seguinte",
                                       "R$/aluno", "estimativa", f"{fe}; {fc}"),
        "vl_fundeb_por_aluno_est": Col("Receita do governo estadual ÷ matrículas da rede estadual na UF "
                                       "(mesmo valor para todos os municípios da UF). PROVISÓRIO, como acima",
                                       "R$/aluno", "estimativa", f"{fe}; {fc}"),
        "pct_uniao_mun": Col("vl_compl_uniao_mun ÷ vl_receita_total_mun", "proporção (0–1)", "calculado", fe),
        "pct_uniao_est": Col("Complementação da União ÷ receita total do governo estadual",
                             "proporção (0–1)", "calculado", fe),
        "afetados_fundeb_complementacao": Col(
            "Matrículas das redes (municipal e/ou estadual no município) que recebem alguma "
            "complementação da União (VAAF, VAAT ou VAAR)", "matrículas", "calculado", f"{fe}; {fc}"),
        "perda_fundeb_sem_uniao": Col("Complementação da União que deixaria de chegar: rede municipal "
                                      "(publicado) + rede estadual (rateio)", "R$", "estimativa", fe),
        "risco_perda_vaar": Col("Verdadeiro se a rede municipal recebe VAAR (depende de condicionalidades)",
                                "booleano", "calculado", fe),
        "vl_fundeb_total_mun_mais_est": Col("vl_receita_total_mun + vl_receita_total_est (inclui rateio)",
                                            "R$", "estimativa", fe),
        "ano_ref": Col("Exercício do Fundeb", "ano", "referencia", fe),
        "ano_ref_censo": COMUNS["ano_ref_censo"],
        "fonte_ato": DIC_ENTES["fonte_ato"],
    }
    for c in VL:
        base = DIC_ENTES[c]
        d[f"{c}_mun"] = Col(base.descricao + " — rede municipal", base.unidade, "publicado", fe)
        d[f"{c}_est"] = Col(base.descricao + f" — rede estadual no município. {rateio}",
                            base.unidade, "estimativa", fe)
    for c in ["recebe_vaaf", "recebe_vaat", "recebe_vaar"]:
        base = DIC_ENTES[c]
        d[f"{c}_mun"] = Col(base.descricao + " — rede municipal", "booleano", "calculado", fe)
        d[f"{c}_est"] = Col(base.descricao + " — governo estadual da UF", "booleano", "calculado", fe)
    return d


if __name__ == "__main__":
    o = run()
    print(f"municípios: {len(o):,} | com rede municipal no Fundeb: {o.vl_receita_total_mun.notna().sum():,}")
    print(f"receita municipal: R$ {o.vl_receita_total_mun.sum()/1e9:,.3f} bi | "
          f"estadual rateada: R$ {o.vl_receita_total_est.sum()/1e9:,.3f} bi")
    print(f"perda sem União (soma): R$ {o.perda_fundeb_sem_uniao.sum()/1e9:,.3f} bi")
    print(f"afetados complementação: {o.afetados_fundeb_complementacao.sum():,}")
    print("vl por aluno municipal (mediana):", round(o.vl_fundeb_por_aluno_mun.median(), 2))
    print(o.vl_fundeb_por_aluno_mun.describe().round(0).to_dict())
    print("sem VAAT calculado:", int(o.sem_vaat_calculado_mun.sum()))
