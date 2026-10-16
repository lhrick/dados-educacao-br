"""Fase 1.4 — Fomento à criação de matrículas em tempo integral (ETI), ciclo 2025.

Desde a EC 135/2024 o fomento ETI sai da complementação da União ao Fundeb: a Portaria
MEC nº 586/2025 destinou R$ 3.053.316.945,67 em 2025, deduzidos do VAAF/VAAT/VAAR.
Não é dinheiro novo em relação ao Fundeb do mesmo ano — não somar com o Fundeb 2025.

Fontes (DOU, versão HTML — as tabelas saem limpas, ao contrário do PDF):
- Portaria MEC nº 605/2025, Anexo: por rede, quantidade de matrículas fomentadas, valor
  total e se registrou política de tempo integral;
- Portaria MEC nº 823/2025, Anexo II: versão vigente (retificada) do cronograma por rede
  (out/2025 a jan/2026), que substituiu o da Portaria nº 669/2025.

Saída: data/interim/eti_redes_2025.parquet — uma linha por rede (ente × rede).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

from src import dicionario
from src.dicionario import Col
from src.manifest import INTERIM, RAW, baixar

ANO = 2025
TOTAL_PORTARIA_586 = 3_053_316_945.67
DOU = "https://www.in.gov.br/web/dou/-/"
P605 = "portaria-mec-n-605-de-29-de-agosto-de-2025-652034216"
P823 = "portaria-mec-n-823-de-12-de-dezembro-de-2025-675518888"
FONTE = "DOU — Imprensa Nacional (fomento tempo integral)"

CAB_605 = ["Código IBGE", "UF", "Ente", "Rede", "Registrou política e norma de Ed. Integral em Tempo Integral",
           "Valor total do fomento a ser repassado", "Quantidade de matrículas"]
CAB_823 = ["Código IBGE", "UF", "Ente", "Rede", "Valor total do fomento a ser repassado",
           "Valor de repasse em outubro de 2025", "Valor de repasse em novembro de 2025",
           "Valor de repasse em dezembro de 2025 (retificado)", "Valor de repasse em janeiro de 2026 (retificado)"]


def _celulas(tr: str) -> list[str]:
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]


def _tabela(slug: str, cabecalho: list[str]) -> pd.DataFrame:
    p = baixar(FONTE, DOU + slug, RAW / "dou" / f"{slug}.html", ano_ref=ANO)
    t = p.read_text(encoding="utf-8", errors="replace")
    linhas = [_celulas(tr) for tr in re.findall(r"<tr.*?</tr>", t, re.S)]
    assert cabecalho in linhas, f"cabeçalho esperado não encontrado em {slug}"
    dados = [l for l in linhas if len(l) == len(cabecalho) and re.fullmatch(r"\d{2}|\d{7}", l[0])]
    return pd.DataFrame(dados, columns=cabecalho)


def _reais(s: pd.Series) -> pd.Series:
    """'R$ 1.234,56' -> 1234.56; 'R$ -' ou '-' (rede sem fomento) -> 0."""
    s = s.str.replace("R$", "", regex=False).str.strip()
    s = s.where(s != "-", "0")
    return pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))


def run() -> pd.DataFrame:
    a = _tabela(P605, CAB_605)
    b = _tabela(P823, CAB_823)
    a = pd.DataFrame({
        "cod_ibge": a["Código IBGE"], "uf": a["UF"], "ente": a["Ente"], "rede": a["Rede"].str.lower(),
        "registrou_politica_eti": a[CAB_605[4]].map({"Sim": True, "Não": False}),
        "vl_fomento_eti_605": _reais(a[CAB_605[5]]),
        "qtd_matriculas_eti": _reais(a[CAB_605[6]]).astype("int64"),
    })
    meses = {"out_2025": CAB_823[5], "nov_2025": CAB_823[6], "dez_2025": CAB_823[7], "jan_2026": CAB_823[8]}
    b = pd.DataFrame({"cod_ibge": b["Código IBGE"], "rede": b["Rede"].str.lower(),
                      "vl_fomento_eti": _reais(b[CAB_823[4]]),
                      **{f"vl_eti_{k}": _reais(b[v]) for k, v in meses.items()}})

    assert a.registrou_politica_eti.notna().all()
    assert not a.duplicated(["cod_ibge", "rede"]).any() and not b.duplicated(["cod_ibge", "rede"]).any()
    out = a.merge(b, on=["cod_ibge", "rede"], how="outer", validate="one_to_one", indicator=True)
    # A 823 só lista redes com fomento; as ausentes têm de ter zero na 605.
    assert not (out._merge == "right_only").any()
    so_605 = out._merge == "left_only"
    assert (out.loc[so_605, "vl_fomento_eti_605"] == 0).all() and (out.loc[so_605, "qtd_matriculas_eti"] == 0).all()
    vl_cols = ["vl_fomento_eti"] + [f"vl_eti_{k}" for k in meses]
    out[vl_cols] = out[vl_cols].fillna(0.0)
    out = out.drop(columns="_merge")

    # Conferências: total = Portaria 586; 823 não mudou o total por rede; parcelas somam o total.
    assert abs(out.vl_fomento_eti.sum() - TOTAL_PORTARIA_586) < 1.0, out.vl_fomento_eti.sum()
    assert (out.vl_fomento_eti - out.vl_fomento_eti_605).abs().max() < 0.01
    parcelas = out[[f"vl_eti_{k}" for k in meses]].sum(axis=1)
    assert (parcelas - out.vl_fomento_eti).abs().max() < 0.05
    out = out.drop(columns="vl_fomento_eti_605")

    out["tipo_ente"] = out.cod_ibge.str.len().map({2: "estado", 7: "municipio"})
    assert set(out.rede) <= {"estadual", "municipal"}
    out["vl_fomento_por_matricula_eti"] = out.vl_fomento_eti / out.qtd_matriculas_eti.where(out.qtd_matriculas_eti > 0)
    out["ano_ref"] = ANO
    out.to_parquet(INTERIM / f"eti_redes_{ANO}.parquet", index=False)
    dicionario.salvar(out, DICIONARIO, INTERIM / f"eti_redes_{ANO}.parquet")
    return out


F605 = "Portaria MEC nº 605/2025, Anexo (DOU 29/08/2025, Edição Extra-B)"
F823 = "Portaria MEC nº 823/2025, Anexo II retificado (DOU 16/12/2025)"
DICIONARIO = {
    "cod_ibge": Col("Código IBGE do ente: 2 dígitos = estado/DF; 7 dígitos = município", "código", "chave", F605),
    "uf": Col("Sigla da UF", "texto", "publicado", F605),
    "ente": Col("Nome do ente", "texto", "publicado", F605),
    "rede": Col("Rede de ensino: estadual ou municipal", "categoria", "chave", F605),
    "registrou_politica_eti": Col("Registrou política e norma de educação integral em tempo integral "
                                  "(quem não registrou teve dedução de 45,43% — art. 6º, II, b)",
                                  "booleano", "publicado", F605),
    "qtd_matriculas_eti": Col("Quantidade de matrículas em tempo integral fomentadas na rede (ciclo 2025; "
                              "'-' na fonte = 0)",
                              "matrículas", "publicado", F605),
    "vl_fomento_eti": Col("Valor total do fomento ETI 2025 para a rede (igual ao da Portaria 605; "
                          "sai da complementação da União ao Fundeb)", "R$", "publicado", F823),
    "vl_eti_out_2025": Col("Parcela de outubro/2025", "R$", "publicado", F823),
    "vl_eti_nov_2025": Col("Parcela de novembro/2025", "R$", "publicado", F823),
    "vl_eti_dez_2025": Col("Parcela de dezembro/2025 (retificada)", "R$", "publicado", F823),
    "vl_eti_jan_2026": Col("Parcela de janeiro/2026 (retificada)", "R$", "publicado", F823),
    "tipo_ente": Col("estado ou municipio", "categoria", "calculado", "pipeline"),
    "vl_fomento_por_matricula_eti": Col("vl_fomento_eti ÷ qtd_matriculas_eti", "R$/matrícula", "calculado",
                                        f"{F605}; {F823}"),
    "ano_ref": Col("Ciclo do fomento", "ano", "referencia", F605),
}


if __name__ == "__main__":
    o = run()
    print(o.groupby(["tipo_ente", "rede"]).agg(redes=("cod_ibge", "size"), mat=("qtd_matriculas_eti", "sum"),
                                               vl=("vl_fomento_eti", "sum")))
    print(f"total: R$ {o.vl_fomento_eti.sum():,.2f} | matrículas: {o.qtd_matriculas_eti.sum():,}")
    print("não registraram política:", int((~o.registrou_politica_eti).sum()))
    print("R$/matrícula:", o.vl_fomento_por_matricula_eti.describe().round(2).to_dict())
