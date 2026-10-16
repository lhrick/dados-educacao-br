"""Fase 1.1 — Pé-de-Meia: pagamentos publicados pela CGU (Portal da Transparência).

A API de dados do portal não tem endpoint do Pé-de-Meia; a fonte é o download
mensal em lote (um zip por mês de folha). Ver docs/fontes.md.

Cada linha do CSV é uma PARCELA, não um estudante. Só as colunas não pessoais são
lidas (usecols): NIS, CPF e nomes nunca entram em memória nem em disco derivado.

Saída: data/interim/pe_de_meia_parcelas.parquet
    cod_ibge_7, mes_folha, tipo_incentivo, periodo_incentivo, etapa_ensino,
    qtd_parcelas, vl_parcelas
"""
from __future__ import annotations

import argparse
import os
import re
import unicodedata
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pv
import requests

from src import dicionario
from src.dicionario import COMUNS, Col
from src.manifest import INTERIM, RAW, baixar, ca_bundle

URL = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/pe-de-meia/{aaaamm}_PeDeMeia.zip"
PRIMEIRO_MES = "202403"
CORRECOES = Path(__file__).with_name("siafi_ibge_correcoes.csv")

COLUNAS = {
    "MÊS FOLHA": "mes_folha",
    "UF": "uf",
    "CÓDIGO MUNICÍPIO SIAFI": "cod_siafi",
    "NOME MUNICÍPIO": "nome_siafi",
    "TIPO INCENTIVO": "tipo_incentivo",
    "PERÍODO INCENTIVO": "periodo_incentivo",
    "ETAPA ENSINO": "etapa_ensino",
    "VALOR PARCELA": "valor_parcela",
}
FONTE = ("CGU — Portal da Transparência, Pé-de-Meia, arquivos mensais "
         "dadosabertos-download.cgu.gov.br/.../pe-de-meia/AAAAMM_PeDeMeia.zip")
DICIONARIO = {
    "cod_ibge_7": Col("Código IBGE do município (convertido do código SIAFI da fonte por UF + nome; "
                      "ver siafi_ibge_correcoes.csv)", "código", "chave", FONTE),
    "mes_folha": Col("Mês da folha de pagamento (MÊS FOLHA)", "AAAAMM", "publicado", FONTE),
    "tipo_incentivo": Col("Tipo de incentivo (TIPO INCENTIVO): Matrícula, Frequência, Conclusão, Enem",
                          "categoria", "publicado", FONTE),
    "periodo_incentivo": Col("Período a que a parcela se refere (PERÍODO INCENTIVO): mês da frequência "
                             "ou 'Ano letivo AAAA'", "texto", "publicado", FONTE),
    "etapa_ensino": Col("Etapa de ensino do estudante (ETAPA ENSINO)", "categoria", "publicado", FONTE),
    "qtd_parcelas": Col("Número de parcelas pagas (valor > 0) no grupo; uma linha = uma parcela, "
                        "não um estudante", "parcelas", "calculado", FONTE),
    "qtd_estornos": Col("Número de linhas com valor negativo (estornos/devoluções) no grupo", "parcelas",
                        "calculado", FONTE),
    "vl_parcelas": Col("Soma do VALOR PARCELA no grupo, líquida de estornos", "R$", "calculado", FONTE),
}
GRUPO = ["mes_folha", "uf", "cod_siafi", "nome_siafi", "tipo_incentivo",
         "periodo_incentivo", "etapa_ensino"]


def _meses(ate: str) -> list[str]:
    ini = pd.Period(f"{PRIMEIRO_MES[:4]}-{PRIMEIRO_MES[4:]}", "M")
    fim = pd.Period(f"{ate[:4]}-{ate[4:]}", "M")
    return [p.strftime("%Y%m") for p in pd.period_range(ini, fim, freq="M")]


def _publicado(aaaamm: str) -> bool:
    # O servidor responde 403 (não 404) para meses inexistentes e 405 a HEAD;
    # GET em streaming, fechado sem ler o corpo.
    with requests.get(URL.format(aaaamm=aaaamm), stream=True, timeout=30, verify=ca_bundle()) as r:
        return r.status_code == 200


def _ler_mes(zpath: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as zf:
        (membro,) = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        with zf.open(membro) as f:
            # Leitor do pyarrow (multithread). Tipos declarados como string na
            # leitura: pd.read_csv(engine="pyarrow", dtype=str) infere antes e
            # perde o zero à esquerda do código SIAFI ("0377" -> "377").
            tabela = pv.read_csv(
                f,
                read_options=pv.ReadOptions(encoding="latin-1"),
                parse_options=pv.ParseOptions(delimiter=";"),
                convert_options=pv.ConvertOptions(
                    include_columns=list(COLUNAS),
                    column_types={c: pa.string() for c in COLUNAS},
                ),
            )
    df = tabela.to_pandas().rename(columns=COLUNAS)
    assert df["cod_siafi"].str.fullmatch(r"\d{4}").all(), "código SIAFI fora do padrão de 4 dígitos"
    df["valor_parcela"] = pd.to_numeric(
        df["valor_parcela"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="raise",
    )
    # Estornos vêm como parcelas negativas (até 2026-10 só em Conclusão, R$ -1.000).
    df["estorno"] = df["valor_parcela"] < 0
    return (
        df.groupby(GRUPO, as_index=False, dropna=False)
        .agg(qtd_parcelas=("estorno", lambda s: int((~s).sum())), qtd_estornos=("estorno", "sum"),
             vl_parcelas=("valor_parcela", "sum"))
    )


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def siafi_para_ibge(pares: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Mapeia (uf, cod_siafi, nome_siafi) -> cod_ibge_7.

    Casa por UF + nome normalizado; grafias divergentes vêm de
    siafi_ibge_correcoes.csv (nome IBGE atual, resolvido contra a ref do IBGE).
    """
    ref = ref.assign(k=ref.uf + "|" + ref.municipio.map(_norm))
    assert ref.k.is_unique
    corr = pd.read_csv(CORRECOES, sep=";", dtype=str)
    corr = corr.merge(ref[["uf", "municipio", "cod_ibge_7"]],
                      left_on=["uf", "municipio_ibge"], right_on=["uf", "municipio"], how="left")
    assert corr.cod_ibge_7.notna().all(), corr[corr.cod_ibge_7.isna()]

    p = pares[["uf", "cod_siafi", "nome_siafi"]].drop_duplicates("cod_siafi").copy()
    p["k"] = p.uf + "|" + p.nome_siafi.map(_norm)
    p = p.merge(ref[["k", "cod_ibge_7"]], on="k", how="left").drop(columns="k")
    p = p.merge(corr[["cod_siafi", "cod_ibge_7"]].rename(columns={"cod_ibge_7": "corr"}),
                on="cod_siafi", how="left")
    p["cod_ibge_7"] = p["cod_ibge_7"].fillna(p.pop("corr"))

    sem = p[p.cod_ibge_7.isna()]
    if len(sem):
        raise ValueError(f"códigos SIAFI sem IBGE (adicionar em {CORRECOES.name}):\n{sem}")
    assert p.cod_ibge_7.is_unique, "dois códigos SIAFI caíram no mesmo IBGE"
    return p[["cod_siafi", "cod_ibge_7"]]


def run(ate: str | None = None, workers: int = 4) -> pd.DataFrame:
    ate = ate or date.today().strftime("%Y%m")
    zips = {}
    for aaaamm in _meses(ate):
        zpath = RAW / "cgu" / "pe_de_meia" / f"{aaaamm}_PeDeMeia.zip"
        if not zpath.exists() and not _publicado(aaaamm):
            # 403 = mês não publicado; 405 + x-amzn-waf-action = captcha (baixar à mão)
            print(f"{aaaamm}: indisponível (não publicado ou bloqueado por captcha)")
            continue
        baixar("CGU Portal da Transparência — Pé-de-Meia", URL.format(aaaamm=aaaamm),
               zpath, ano_ref=aaaamm[:4])
        zips[aaaamm] = zpath

    # Meses são independentes: lê em paralelo (~1,3 GB de RAM por worker).
    workers = max(1, min(workers, len(zips), os.cpu_count() or 1))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        partes = list(ex.map(_ler_mes, zips.values()))
    for aaaamm, parte in zip(zips, partes):
        print(f"{aaaamm}: {int(parte.qtd_parcelas.sum()):,} parcelas")

    agg = pd.concat(partes, ignore_index=True)
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")
    mapa = siafi_para_ibge(agg, ref)
    out = agg.merge(mapa, on="cod_siafi", how="left", validate="many_to_one")
    out = (
        out.groupby(["cod_ibge_7"] + GRUPO[:1] + GRUPO[4:], as_index=False)
        [["qtd_parcelas", "qtd_estornos", "vl_parcelas"]].sum()
    )
    # A contagem de beneficiários usa parcelas de Matrícula: estorno de Matrícula quebraria o critério.
    est_mat = out.loc[out.tipo_incentivo == "Matrícula", "qtd_estornos"].sum()
    assert est_mat == 0, f"{est_mat} estornos de Matrícula — revisar critério de beneficiários"
    out.to_parquet(INTERIM / "pe_de_meia_parcelas.parquet", index=False)
    dicionario.salvar(out, DICIONARIO, INTERIM / "pe_de_meia_parcelas.parquet")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ate", help="último mês de folha AAAAMM (padrão: mês atual)")
    ap.add_argument("--workers", type=int, default=4, help="meses lidos em paralelo")
    args = ap.parse_args()
    out = run(args.ate, args.workers)
    print(out.groupby("tipo_incentivo")[["qtd_parcelas", "vl_parcelas"]].sum())
