"""Fase 1.3 — Fundeb 2026: estimativas por ente federado (FNDE).

Fonte vigente: anexos da Portaria Interministerial MEC/MF nº 6, de 29/04/2026, que
substituiu os Anexos I a VII da Portaria nº 14/2025 (revisão quadrimestral). O FNDE
publica os anexos em CSV na "2ª publicação" de 2026. Ver docs/fontes.md.

Ente = governo estadual (cod_ibge de 2 dígitos = código da UF) ou município (7 dígitos).
O DF aparece só como ente estadual (53).

Saída: data/interim/fundeb_entes_2026.parquet — uma linha por ente.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from src import dicionario
from src.dicionario import Col
from src.manifest import INTERIM, RAW, baixar

ANO = 2026
FONTE = "FNDE Fundeb 2026 — Anexos Portaria Interministerial MEC/MF nº 6/2026"
BASE = ("https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/"
        "fundeb/2026-1/publicacoes-2026/2-publicacao/")
ANEXOS = {
    "receita": "1-receita-total-do-fundeb-por-ente-federado",
    "vaat": "3-vaat-vaat-min-e-complementacao-vaat-por-ente-federado",
    "vaar": "6-redes-beneficiadas-coef-de-distribuicao-e-compl-vaar-prevista",
}


A1 = "FNDE — Anexo I (receita total por ente), Portaria Interministerial MEC/MF nº 6/2026"
A3 = "FNDE — Anexo III (VAAT por ente), Portaria Interministerial MEC/MF nº 6/2026"
A6 = "FNDE — Anexo VI (redes beneficiadas VAAR), Portaria Interministerial MEC/MF nº 6/2026"
DICIONARIO = {
    "uf": Col("Sigla da UF do ente", "texto", "publicado", A1),
    "cod_ibge": Col("Código IBGE do ente: 2 dígitos = governo estadual (código da UF); "
                    "7 dígitos = município", "código", "chave", A1),
    "ente": Col("Nome do ente como publicado pelo FNDE", "texto", "publicado", A1),
    "vl_contribuicao_ente": Col("Receita estimada da contribuição de estados e municípios ao Fundeb "
                                "destinada ao ente em 2026", "R$", "publicado", A1),
    "vl_compl_vaaf": Col("Complementação da União VAAF estimada para 2026", "R$", "publicado", A1),
    "vl_compl_vaat": Col("Complementação da União VAAT estimada para 2026", "R$", "publicado", A1),
    "vl_compl_vaar": Col("Complementação da União VAAR estimada para 2026", "R$", "publicado", A1),
    "vl_compl_uniao": Col("Complementação da União total (VAAF + VAAT + VAAR)", "R$", "publicado", A1),
    "vl_receita_total": Col("Total das receitas previstas do Fundeb para o ente em 2026", "R$",
                            "publicado", A1),
    "vaat_antes_compl": Col("VAAT anterior à complementação-VAAT (art. 16, IV, Lei 14.113/2020); "
                            "vazio = VAAT não calculado para o ente", "R$/aluno", "publicado", A3),
    "vaat_com_compl": Col("VAAT com a complementação da União-VAAT (art. 16, V)", "R$/aluno",
                          "publicado", A3),
    "pct_iei": Col("Indicador de Educação Infantil: % da complementação-VAAT vinculado à educação "
                   "infantil (art. 16, VII)", "%", "publicado", A3),
    "coef_vaar": Col("Coeficiente de distribuição da complementação-VAAR (vazio = rede não beneficiada)",
                     "coeficiente", "publicado", A6),
    "tipo_ente": Col("estado (governo estadual/DF) ou municipio", "categoria", "calculado", "pipeline"),
    "rede": Col("Rede correspondente ao ente: estadual ou municipal", "categoria", "calculado", "pipeline"),
    "recebe_vaaf": Col("Verdadeiro se vl_compl_vaaf > 0", "booleano", "calculado", A1),
    "recebe_vaat": Col("Verdadeiro se vl_compl_vaat > 0", "booleano", "calculado", A1),
    "recebe_vaar": Col("Verdadeiro se vl_compl_vaar > 0", "booleano", "calculado", A1),
    "pct_uniao": Col("vl_compl_uniao ÷ vl_receita_total", "proporção (0–1)", "calculado", A1),
    "ano_ref": Col("Exercício do Fundeb", "ano", "referencia", A1),
    "fonte_ato": Col("Ato normativo de origem dos valores", "texto", "referencia", A1),
}


def _baixar(nome: str) -> Path:
    return baixar(FONTE, BASE + nome + ".csv/@@download/file",
                  RAW / "fnde" / "fundeb_2026" / f"anexo_{nome}.csv", ano_ref=ANO)


def _num(s: pd.Series) -> pd.Series:
    """' 18.707.652,69 ' -> 18707652.69; ' -   ' -> 0; '53,50%' -> 53.5."""
    s = s.fillna("").str.strip().str.rstrip("%").str.strip()
    s = s.where(~s.isin(["-", ""]), "0")
    return pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                         errors="raise")


def _ler(path: Path) -> tuple[pd.DataFrame, list[str] | None]:
    """Lê o anexo pulando o título; devolve (linhas de entes, linha TOTAL ou None)."""
    with open(path, encoding="latin-1", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    i = next(i for i, r in enumerate(rows) if any(c.strip().upper() == "UF" for c in r))
    cab = [" ".join(c.split()) for c in rows[i]]
    n = max(j for j, c in enumerate(cab) if c) + 1
    corpo = [r[:n] for r in rows[i + 1:] if any(c.strip() for c in r)]
    # O rótulo "TOTAL" aparece na 1ª ou na 3ª coluna, conforme o anexo.
    eh_total = lambda r: any(c.strip().upper() == "TOTAL" for c in r[:3])
    total = next((r for r in corpo if eh_total(r)), None)
    entes = [r for r in corpo if not eh_total(r)]
    df = pd.DataFrame(entes, columns=cab[:n]).apply(lambda c: c.str.strip())
    return df, total


def _confere_total(df: pd.DataFrame, total: list[str] | None, cols: list[str], nome: str) -> None:
    assert total is not None, f"{nome}: linha TOTAL não encontrada"
    rot = next(j for j, c in enumerate(total[:3]) if c.strip().upper() == "TOTAL")
    vals = [c.strip() for c in total[rot + 1:] if c.strip()]
    esperado = _num(pd.Series(vals[: len(cols)]))
    for c, e in zip(cols, esperado):
        soma = df[c].sum()
        assert abs(soma - e) < 1.0, f"{nome}: soma de '{c}' = {soma:,.2f} ≠ TOTAL {e:,.2f}"


def ler_receita() -> pd.DataFrame:
    df, total = _ler(_baixar(ANEXOS["receita"]))
    mapa = {
        "Código IBGE": "cod_ibge",
        "Entidade": "ente",
        "Receita da contribuição de estados e municípios ao Fundeb": "vl_contribuicao_ente",
        "Complementação VAAF": "vl_compl_vaaf",
        "Complementação VAAT": "vl_compl_vaat",
        "Complementação VAAR": "vl_compl_vaar",
        "Complementação da União Total": "vl_compl_uniao",
        "Total das receitas previstas": "vl_receita_total",
    }
    df = df.rename(columns={"UF": "uf", **mapa})[["uf", *mapa.values()]]
    vl = [c for c in df if c.startswith("vl_")]
    df[vl] = df[vl].apply(_num)
    _confere_total(df, total, vl, "Anexo I")
    return df


def ler_vaat() -> pd.DataFrame:
    df, _ = _ler(_baixar(ANEXOS["vaat"]))
    cols = list(df.columns)
    df = df.rename(columns={
        cols[2]: "cod_ibge",
        next(c for c in cols if c.startswith("VAAT anterior")): "vaat_antes_compl",
        next(c for c in cols if c.startswith("VAAT com")): "vaat_com_compl",
        next(c for c in cols if c.startswith("Indicador de Educação Infantil")): "pct_iei",
    })[["cod_ibge", "vaat_antes_compl", "vaat_com_compl", "pct_iei"]]
    for c in ["vaat_antes_compl", "vaat_com_compl", "pct_iei"]:
        df[c] = _num(df[c])
    return df


def ler_vaar() -> pd.DataFrame:
    df, total = _ler(_baixar(ANEXOS["vaar"]))
    cols = list(df.columns)
    df = df.rename(columns={cols[2]: "cod_ibge", cols[3]: "coef_vaar", cols[4]: "vl_compl_vaar_anexo6"})
    df = df[["cod_ibge", "coef_vaar", "vl_compl_vaar_anexo6"]]
    df["coef_vaar"] = _num(df["coef_vaar"])
    df["vl_compl_vaar_anexo6"] = _num(df["vl_compl_vaar_anexo6"])
    # Anexo VI não tem linha TOTAL: os coeficientes de distribuição somam 1.
    assert total is None
    assert abs(df["coef_vaar"].sum() - 1) < 1e-6, df["coef_vaar"].sum()
    return df


def run() -> pd.DataFrame:
    rec = ler_receita()
    out = (rec.merge(ler_vaat(), on="cod_ibge", how="left", validate="one_to_one")
              .merge(ler_vaar(), on="cod_ibge", how="left", validate="one_to_one"))

    assert out.cod_ibge.str.fullmatch(r"\d{2}|\d{7}").all()
    out["tipo_ente"] = out.cod_ibge.str.len().map({2: "estado", 7: "municipio"})
    out["rede"] = out.tipo_ente.map({"estado": "estadual", "municipio": "municipal"})

    # Consistência interna do Anexo I e entre anexos.
    soma_compl = out[["vl_compl_vaaf", "vl_compl_vaat", "vl_compl_vaar"]].sum(axis=1)
    assert (soma_compl - out.vl_compl_uniao).abs().max() < 0.05
    assert (out.vl_contribuicao_ente + out.vl_compl_uniao - out.vl_receita_total).abs().max() < 0.05
    vaar = out.vl_compl_vaar_anexo6.fillna(0)
    assert (vaar - out.vl_compl_vaar).abs().max() < 0.05, "VAAR do Anexo I ≠ Anexo VI"
    out = out.drop(columns="vl_compl_vaar_anexo6")

    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")
    mun = out[out.tipo_ente == "municipio"]
    assert mun.cod_ibge.isin(ref.cod_ibge_7).all(), mun[~mun.cod_ibge.isin(ref.cod_ibge_7)]
    assert out.cod_ibge.is_unique

    out["recebe_vaaf"] = out.vl_compl_vaaf > 0
    out["recebe_vaat"] = out.vl_compl_vaat > 0
    out["recebe_vaar"] = out.vl_compl_vaar > 0
    out["pct_uniao"] = out.vl_compl_uniao / out.vl_receita_total.where(out.vl_receita_total > 0)
    out["ano_ref"] = ANO
    out["fonte_ato"] = "Portaria Interministerial MEC/MF nº 6/2026"
    out.to_parquet(INTERIM / f"fundeb_entes_{ANO}.parquet", index=False)
    dicionario.salvar(out, DICIONARIO, INTERIM / f"fundeb_entes_{ANO}.parquet")
    return out


if __name__ == "__main__":
    out = run()
    print(out.groupby("tipo_ente").size().to_dict())
    vl = [c for c in out if c.startswith("vl_")]
    print((out[vl].sum() / 1e9).round(3).astype(str) + " bi")
    print("recebem VAAF/VAAT/VAAR:", out[["recebe_vaaf", "recebe_vaat", "recebe_vaar"]].sum().to_dict())
    print("municípios sem VAAT no anexo III:", out[(out.tipo_ente == "municipio") & out.vaat_com_compl.isna()].shape[0])
