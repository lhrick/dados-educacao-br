"""Fase 4 — Tabela consolidada de educação por município (uma linha por município).

Cada coluna vem de uma tabela intermediária (mapa ORIGEM); o dicionário consolidado é
montado a partir dos dicionários dessas tabelas — nunca escrito à mão.

Regra do CLAUDE.md: nunca somar alunos entre programas. Cada programa tem sua coluna
`afetados_*`; o total de alunos distintos é só `qtd_alunos_rede_publica` (Censo).

Saída: data/processed/educacao_municipios_<ano>.parquet + .csv (+ _dicionario.csv)
"""
from __future__ import annotations

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.ingest import ibge
from src.manifest import INTERIM, PROCESSED
from src.metrics import textos
from src.transform import eti as t_eti
from src.transform import fundeb_repasses as t_fundeb
from src.transform import pe_de_meia as t_pdm
from src.transform import pnld as t_pnld

ANO = 2025

# tabela intermediária -> (função do dicionário, {coluna_final: coluna_origem})
ORIGEM = {
    f"pe_de_meia_municipio_{ANO}": (lambda: t_pdm.dicionario_(ANO), {
        "qtd_beneficiarios_pe_de_meia": "qtd_beneficiarios_pe_de_meia",
        "afetados_pe_de_meia": "afetados_pe_de_meia",
        "vl_pago_pe_de_meia": "vl_pago_pe_de_meia",
        "vl_por_aluno_pe_de_meia": "vl_por_aluno_pe_de_meia",
        "vl_conclusao_pe_de_meia": "vl_conclusao_pe_de_meia",
        "razao_pe_de_meia_censo": "razao_pe_de_meia_censo",
        "flag_pe_de_meia_acima_censo": "flag_pe_de_meia_acima_censo",
    }),
    f"pnld_municipio_{ANO}": (t_pnld.dicionario_, {
        "afetados_pnld": "afetados_pnld",
        "vl_pnld_total_est": "vl_pnld_total_est",
        "vl_pnld_por_aluno_est": "vl_pnld_por_aluno_est",
        "flag_pnld_cobertura_baixa_uf": "flag_pnld_cobertura_baixa_uf",
    }),
    f"fundeb_municipio_{ANO}": (lambda: t_fundeb.dicionario_(ANO), {
        "mat_rede_municipal": "mat_rede_municipal",
        "mat_rede_estadual": "mat_rede_estadual",
        "vl_fundeb_rede_municipal": "vl_receita_mun",
        "vl_fundeb_uniao_rede_municipal": "vl_compl_uniao_mun",
        "pct_uniao_rede_municipal": "pct_uniao_mun",
        "vl_fundeb_por_aluno_rede_municipal": "vl_fundeb_por_aluno_mun",
        "vl_fundeb_rede_estadual_est": "vl_receita_est",
        "vl_fundeb_uniao_rede_estadual_est": "vl_compl_uniao_est",
        "afetados_fundeb_complementacao": "afetados_fundeb_complementacao",
        "perda_fundeb_sem_uniao": "perda_fundeb_sem_uniao",
        "risco_perda_vaar": "risco_perda_vaar",
        "recebe_vaaf_rede_municipal": "recebe_vaaf_mun",
        "recebe_vaat_rede_municipal": "recebe_vaat_mun",
        "recebe_vaar_rede_municipal": "recebe_vaar_mun",
    }),
    f"eti_municipio_{ANO}": (t_eti.dicionario_, {
        "afetados_eti": "afetados_eti",
        "qtd_matriculas_eti_rede_municipal": "qtd_matriculas_eti_mun",
        "vl_fomento_eti_rede_municipal": "vl_fomento_eti_mun",
        "vl_fomento_eti_rede_estadual_est": "vl_fomento_eti_est",
        "registrou_politica_eti_rede_municipal": "registrou_politica_eti_mun",
    }),
}

FC = "INEP — Censo Escolar (ref_matriculas_municipio)"
NOVAS = {
    "cod_ibge_7": COMUNS["cod_ibge_7"], "cod_ibge_6": ibge.DICIONARIO["cod_ibge_6"],
    "municipio": COMUNS["municipio"], "uf": COMUNS["uf"], "regiao": ibge.DICIONARIO["regiao"],
    "qtd_alunos_rede_publica": Col("Matrículas da educação básica nas redes públicas (federal + estadual + "
                                   "municipal) — ÚNICO total de alunos distintos; não somar afetados_*",
                                   "matrículas", "calculado", FC),
    "qtd_escolas_publicas": Col("Escolas públicas em atividade", "escolas", "calculado", FC),
    "mat_em_publico": Col("Matrículas de ensino médio + EJA médio nas redes públicas", "matrículas",
                          "calculado", FC),
    "qtd_escolas_rede_municipal": Col("Escolas municipais em atividade com matrícula na educação básica "
                                      "(qt_mat_bas > 0)", "escolas", "calculado", FC),
    "vl_fundeb_media_por_escola_rede_municipal": Col(
        "MÉDIA por escola: Fundeb da rede municipal ÷ qtd_escolas_rede_municipal. Não é o valor recebido por "
        "cada escola — o Fundeb é pago à rede", "R$/escola", "calculado",
        "fundeb_municipio_2025 (Tesouro) + INEP — Censo Escolar (ref_escolas)"),
    "qtd_escolas_eti_rede_municipal": Col("Escolas municipais em atividade com matrícula em tempo integral "
                                          "(inf + fund + médio integral > 0)", "escolas", "calculado", FC),
    "vl_eti_media_por_escola_rede_municipal": Col(
        "MÉDIA por escola: fomento ETI da rede municipal ÷ qtd_escolas_eti_rede_municipal. Não é o valor "
        "recebido por cada escola — o fomento é pago à rede", "R$/escola", "calculado",
        "eti_municipio_2025 (Portarias MEC 605/823) + INEP — Censo Escolar (ref_escolas)"),
    "txt_afetados_pe_de_meia": Col("Texto pronto (risco): estudantes que deixam de receber se o programa for "
                                   "interrompido (vazio se zero)", "texto", "calculado",
                                   "pipeline (src/metrics/textos.py)"),
    "txt_afetados_fundeb": Col("Texto pronto (risco): alunos em redes que recebem complementação da União "
                               "(afetados_fundeb_complementacao; vazio se zero)", "texto", "calculado",
                               "pipeline (src/metrics/textos.py)"),
    "txt_afetados_eti": Col("Texto pronto (risco): matrículas integrais da rede municipal com fomento (valor "
                            "publicado; vazio se zero)", "texto", "calculado", "pipeline (src/metrics/textos.py)"),
    "txt_pe_de_meia": Col("Texto pronto: estudantes que receberam o Pé-de-Meia (vazio se zero)", "texto",
                          "calculado", "pipeline (src/metrics/textos.py)"),
    "txt_fundeb_uniao": Col("Texto pronto: complementação da União ao Fundeb da rede municipal (valor publicado; "
                            "vazio se zero)", "texto", "calculado", "pipeline (src/metrics/textos.py)"),
    "txt_eti": Col("Texto pronto: fomento ETI e matrículas da rede municipal (valores publicados; vazio se zero)",
                   "texto", "calculado", "pipeline (src/metrics/textos.py)"),
    "ano_ref": Col("Ano de referência dos programas (Pé-de-Meia: ano letivo; Fundeb: repasses; PNLD; ETI: ciclo)",
                   "ano", "referencia", "pipeline"),
    "ano_ref_censo": COMUNS["ano_ref_censo"],
}


def run(ano: int = ANO) -> pd.DataFrame:
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet").drop(columns="ano_ref")
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(m.ano_ref.iloc[0])
    pub = m[m.rede.isin(["federal", "estadual", "municipal"])].groupby("cod_ibge_7").agg(
        qtd_alunos_rede_publica=("qt_mat_bas", "sum"), qtd_escolas_publicas=("n_escolas", "sum"),
        mat_em_publico=("qt_mat_med", "sum"), _eja_med=("qt_mat_eja_med", "sum"))
    pub["mat_em_publico"] += pub.pop("_eja_med")
    out = ref.merge(pub.reset_index(), on="cod_ibge_7", how="left")
    esc = pd.read_parquet(INTERIM / "ref_escolas.parquet")
    esc = esc[esc.rede == "municipal"]
    integral = esc[["qt_mat_inf_int", "qt_mat_fund_int", "qt_mat_med_int"]].sum(axis=1)
    out = out.merge(pd.DataFrame({
        "qtd_escolas_rede_municipal": esc[esc.qt_mat_bas > 0].groupby("cod_ibge_7").size(),
        "qtd_escolas_eti_rede_municipal": esc[integral > 0].groupby("cod_ibge_7").size(),
    }).reset_index().rename(columns={"index": "cod_ibge_7"}), on="cod_ibge_7", how="left")
    for c in ["qtd_escolas_rede_municipal", "qtd_escolas_eti_rede_municipal"]:
        out[c] = out[c].fillna(0).astype("int64")
    for c in ["qtd_alunos_rede_publica", "qtd_escolas_publicas", "mat_em_publico"]:
        out[c] = out[c].fillna(0).astype("int64")

    dic = dict(NOVAS)
    for tabela, (dic_fn, cols) in ORIGEM.items():
        src = pd.read_parquet(INTERIM / f"{tabela}.parquet")
        assert int(src.ano_ref.iloc[0]) == ano, f"{tabela}: ano_ref {src.ano_ref.iloc[0]} ≠ {ano}"
        out = out.merge(src[["cod_ibge_7", *cols.values()]].rename(columns={v: k for k, v in cols.items()}),
                        on="cod_ibge_7", how="left", validate="one_to_one")
        d_src = dic_fn()
        for final, orig in cols.items():
            c = d_src[orig]
            dic[final] = Col(c.descricao, c.unidade, c.tipo, f"{c.fonte} [{tabela}.{orig}]")

    out["txt_pe_de_meia"] = [textos.txt_pe_de_meia(n, mu, ano)
                             for n, mu in zip(out.qtd_beneficiarios_pe_de_meia, out.municipio)]
    out["txt_fundeb_uniao"] = [textos.txt_fundeb_uniao(v, ano) for v in out.vl_fundeb_uniao_rede_municipal]
    out["txt_eti"] = [textos.txt_eti(n, v, ano)
                      for n, v in zip(out.qtd_matriculas_eti_rede_municipal, out.vl_fomento_eti_rede_municipal)]
    out["vl_fundeb_media_por_escola_rede_municipal"] = (
        out.vl_fundeb_rede_municipal / out.qtd_escolas_rede_municipal.where(out.qtd_escolas_rede_municipal > 0))
    out["vl_eti_media_por_escola_rede_municipal"] = (
        out.vl_fomento_eti_rede_municipal.where(out.vl_fomento_eti_rede_municipal > 0)
        / out.qtd_escolas_eti_rede_municipal.where(out.qtd_escolas_eti_rede_municipal > 0))
    out["txt_afetados_pe_de_meia"] = [textos.txt_afetados_pe_de_meia(n, mu)
                                      for n, mu in zip(out.afetados_pe_de_meia, out.municipio)]
    out["txt_afetados_fundeb"] = [textos.txt_afetados_fundeb(n, mu)
                                  for n, mu in zip(out.afetados_fundeb_complementacao, out.municipio)]
    out["txt_afetados_eti"] = [textos.txt_afetados_eti(n, mu)
                               for n, mu in zip(out.qtd_matriculas_eti_rede_municipal, out.municipio)]
    out["ano_ref"] = ano
    out["ano_ref_censo"] = ano_censo

    # Ordem: identificação, Censo, programas, textos, referência.
    ordem = ["cod_ibge_7", "cod_ibge_6", "municipio", "uf", "regiao",
             "qtd_alunos_rede_publica", "qtd_escolas_publicas", "mat_em_publico"]
    ordem += [k for _, cols in ORIGEM.values() for k in cols]
    ordem += ["qtd_escolas_rede_municipal", "vl_fundeb_media_por_escola_rede_municipal",
              "qtd_escolas_eti_rede_municipal", "vl_eti_media_por_escola_rede_municipal"]
    ordem += ["txt_pe_de_meia", "txt_fundeb_uniao", "txt_eti",
              "txt_afetados_pe_de_meia", "txt_afetados_fundeb", "txt_afetados_eti", "ano_ref", "ano_ref_censo"]
    out = out[ordem]
    assert out.cod_ibge_7.is_unique and len(out) == len(ref)

    base = PROCESSED / f"educacao_municipios_{ano}"
    out.to_parquet(base.with_suffix(".parquet"), index=False)
    dicionario.salvar(out, dic, base.with_suffix(".parquet"))
    csv = out.copy()
    vl = [c for c in csv if c.startswith(("vl_", "perda_"))]
    csv[vl] = csv[vl].round(2)
    for c in ["razao_pe_de_meia_censo", "pct_uniao_rede_municipal"]:
        csv[c] = csv[c].round(4)
    for c in ["afetados_pnld", "afetados_eti", "qtd_matriculas_eti_rede_municipal"]:
        csv[c] = csv[c].astype("Int64")
    csv.to_csv(base.with_suffix(".csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    o = run()
    print(o.shape)
    print(o[[c for c in o if c.startswith("afetados_")] + ["qtd_alunos_rede_publica"]].sum().map("{:,.0f}".format))
    for c in [c for c in o if c.startswith("txt_")]:
        print(f"{c}: {(o[c] != '').sum():,} municípios com texto | ex.: {o.loc[o[c] != '', c].iloc[100]}")
