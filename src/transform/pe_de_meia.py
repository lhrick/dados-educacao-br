"""Fase 2a/3 — Pé-de-Meia por município, um ano letivo.

Critério (análise em docs/fontes.md):
- qtd_beneficiarios_pe_de_meia = parcelas de Matrícula do ano letivo (uma por estudante/ano),
  somando todas as folhas (há pagamento retroativo em folhas posteriores);
- vl_pago_pe_de_meia = soma de todas as parcelas cujo período é desse ano letivo
  (matrícula + frequência + conclusão + Enem).

Saída: data/interim/pe_de_meia_municipio_<ano>.parquet — uma linha por município
da ref IBGE (municípios sem pagamento ficam com 0).
"""
from __future__ import annotations

import argparse

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, Col
from src.manifest import INTERIM, PROCESSED

ANO_PADRAO = 2025
TIPOS = {"Matrícula": "matricula", "Frequência": "frequencia", "Conclusão": "conclusao", "Enem": "enem"}
REDES_PUBLICAS = ["federal", "estadual", "municipal"]


def _ano_do_periodo(periodo: pd.Series) -> pd.Series:
    # "Ano letivo 2025", "Março 2025", "Julho/Agosto 2024", "Outubro/Novembro 2024"
    ano = periodo.str.extract(r"(\d{4})$", expand=False)
    assert ano.notna().all(), periodo[ano.isna()].unique()
    return ano.astype(int)


def run(ano: int = ANO_PADRAO) -> pd.DataFrame:
    p = pd.read_parquet(INTERIM / "pe_de_meia_parcelas.parquet")
    assert set(p.tipo_incentivo) <= set(TIPOS), set(p.tipo_incentivo) - set(TIPOS)
    folha_ate = p.mes_folha.max()
    p = p[_ano_do_periodo(p.periodo_incentivo) == ano]

    vl = (p.pivot_table(index="cod_ibge_7", columns="tipo_incentivo", values="vl_parcelas",
                        aggfunc="sum", fill_value=0)
            .rename(columns=lambda t: f"vl_{TIPOS[t]}_pe_de_meia"))
    qtd = (p[p.tipo_incentivo == "Matrícula"].groupby("cod_ibge_7").qtd_parcelas.sum()
             .rename("qtd_beneficiarios_pe_de_meia"))

    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7"]]
    out = ref.merge(qtd, on="cod_ibge_7", how="left").merge(vl, on="cod_ibge_7", how="left")
    for t in TIPOS.values():
        if f"vl_{t}_pe_de_meia" not in out:
            out[f"vl_{t}_pe_de_meia"] = 0.0
    vl_cols = [f"vl_{t}_pe_de_meia" for t in TIPOS.values()]
    out[vl_cols] = out[vl_cols].fillna(0.0)
    out["qtd_beneficiarios_pe_de_meia"] = out["qtd_beneficiarios_pe_de_meia"].fillna(0).astype("int64")
    out["vl_pago_pe_de_meia"] = out[vl_cols].sum(axis=1)
    out["vl_por_aluno_pe_de_meia"] = (
        out.vl_pago_pe_de_meia / out.qtd_beneficiarios_pe_de_meia.where(out.qtd_beneficiarios_pe_de_meia > 0)
    )

    # Validação vs Censo (CLAUDE.md): beneficiários / matrículas de EM público.
    cen = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    ano_censo = int(cen.ano_ref.iloc[0])
    cen = (cen[cen.rede.isin(REDES_PUBLICAS)].groupby("cod_ibge_7")[["qt_mat_med", "qt_mat_eja_med"]].sum()
              .sum(axis=1).rename("mat_em_publico_censo").reset_index())
    out = out.merge(cen, on="cod_ibge_7", how="left")
    out["razao_pe_de_meia_censo"] = (
        out.qtd_beneficiarios_pe_de_meia / out.mat_em_publico_censo.where(out.mat_em_publico_censo > 0)
    )
    out["flag_pe_de_meia_acima_censo"] = out.razao_pe_de_meia_censo > 1

    out["afetados_pe_de_meia"] = out.qtd_beneficiarios_pe_de_meia
    out["ano_ref"] = ano
    out["ano_ref_censo"] = ano_censo
    out["folha_ate"] = folha_ate

    assert len(out) == len(ref) and out.cod_ibge_7.is_unique
    out.to_parquet(INTERIM / f"pe_de_meia_municipio_{ano}.parquet", index=False)
    dicionario.salvar(out, dicionario_(ano), INTERIM / f"pe_de_meia_municipio_{ano}.parquet")
    salvar_csv(out, ano)
    return out


def salvar_csv(out: pd.DataFrame, ano: int) -> None:
    """CSV para análise no padrão do time de redação: UTF-8, ';', decimal ','.

    utf-8-sig (UTF-8 com BOM) para o Excel abrir os acentos corretamente.
    """
    nomes = pd.read_parquet(INTERIM / "ref_municipios.parquet")[["cod_ibge_7", "municipio", "uf"]]
    csv = nomes.merge(out, on="cod_ibge_7", how="right", validate="one_to_one")
    vl = [c for c in csv if c.startswith("vl_")]
    csv[vl] = csv[vl].round(2)
    csv["razao_pe_de_meia_censo"] = csv["razao_pe_de_meia_censo"].round(4)
    csv["mat_em_publico_censo"] = csv["mat_em_publico_censo"].astype("Int64")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    destino = PROCESSED / f"pe_de_meia_municipio_{ano}.csv"
    csv.to_csv(destino, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    dicionario.salvar(csv, {"municipio": COMUNS["municipio"], "uf": COMUNS["uf"], **dicionario_(ano)}, destino)


def dicionario_(ano: int) -> dict[str, Col]:
    f = "CGU — Portal da Transparência, Pé-de-Meia (pe_de_meia_parcelas)"
    fc = "INEP — Censo Escolar (ref_matriculas_municipio)"
    al = f"ano letivo {ano}, todas as folhas publicadas"
    return {
        "cod_ibge_7": COMUNS["cod_ibge_7"],
        "qtd_beneficiarios_pe_de_meia": Col(
            f"Estudantes beneficiários = parcelas de Matrícula do {al} (uma por estudante/ano; "
            "proxy — a fonte não permite deduplicar estudantes)", "estudantes", "calculado", f),
        "vl_conclusao_pe_de_meia": Col(f"Valor das parcelas de Conclusão do {al} (depósito na poupança, "
                                       "saque só ao concluir o EM)", "R$", "calculado", f),
        "vl_enem_pe_de_meia": Col(f"Valor das parcelas de Enem do {al}", "R$", "calculado", f),
        "vl_frequencia_pe_de_meia": Col(f"Valor das parcelas de Frequência do {al}", "R$", "calculado", f),
        "vl_matricula_pe_de_meia": Col(f"Valor das parcelas de Matrícula do {al}", "R$", "calculado", f),
        "vl_pago_pe_de_meia": Col(f"Soma de todas as parcelas do {al} (matrícula + frequência + "
                                  "conclusão + Enem)", "R$", "calculado", f),
        "vl_por_aluno_pe_de_meia": Col("vl_pago_pe_de_meia ÷ qtd_beneficiarios_pe_de_meia "
                                       "(vazio se não há beneficiário)", "R$/estudante", "calculado", f),
        "mat_em_publico_censo": Col("Matrículas de ensino médio + EJA médio nas redes públicas "
                                    "(qt_mat_med + qt_mat_eja_med)", "matrículas", "calculado", fc),
        "razao_pe_de_meia_censo": Col("qtd_beneficiarios ÷ mat_em_publico_censo (anos podem diferir: "
                                      "ver ano_ref e ano_ref_censo)", "razão", "calculado", "pipeline"),
        "flag_pe_de_meia_acima_censo": Col("Verdadeiro se razao_pe_de_meia_censo > 1 (checagem do "
                                           "CLAUDE.md; conferir antes de publicar)", "booleano",
                                           "calculado", "pipeline"),
        "afetados_pe_de_meia": Col("Estudantes afetados por corte do programa = qtd_beneficiarios_pe_de_meia",
                                   "estudantes", "calculado", f),
        "ano_ref": Col("Ano letivo dos pagamentos", "ano", "referencia", f),
        "ano_ref_censo": COMUNS["ano_ref_censo"],
        "folha_ate": Col("Última folha de pagamento considerada", "AAAAMM", "referencia", f),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=ANO_PADRAO)
    out = run(ap.parse_args().ano)
    print(f"municípios: {len(out):,} | com beneficiário: {(out.qtd_beneficiarios_pe_de_meia > 0).sum():,}")
    print(f"beneficiários: {out.qtd_beneficiarios_pe_de_meia.sum():,} | "
          f"valor pago: R$ {out.vl_pago_pe_de_meia.sum():,.2f}")
    print(out[[c for c in out if c.startswith("vl_") and c != "vl_por_aluno_pe_de_meia"]].sum().map("{:,.2f}".format))
    print(f"razão > 1 vs Censo {out.ano_ref_censo.iloc[0]}: {out.flag_pe_de_meia_acima_censo.sum()}")
    print("vl_por_aluno (mediana):", round(out.vl_por_aluno_pe_de_meia.median(), 2))
