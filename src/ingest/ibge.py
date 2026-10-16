"""Fase 0.1 — Tabela de referência de municípios (API de localidades do IBGE).

Saída: data/interim/ref_municipios.parquet
    cod_ibge_7, cod_ibge_6, municipio, uf, regiao, ano_ref
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from src import dicionario
from src.dicionario import COMUNS, FONTE_IBGE, Col
from src.manifest import INTERIM, RAW, baixar

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
# 5.570 até 2024; Boa Esperança do Norte (MT, 5101837) foi instalado depois e
# a API passou a retornar 5.571. Ver docs/fontes.md.
N_MUNICIPIOS = 5571


def _uf(m: dict) -> dict:
    # Municípios recentes podem vir sem microrregião; regiao-imediata sempre traz a UF.
    if m.get("microrregiao"):
        return m["microrregiao"]["mesorregiao"]["UF"]
    return m["regiao-imediata"]["regiao-intermediaria"]["UF"]


def run() -> pd.DataFrame:
    hoje = date.today().isoformat()
    destino = RAW / "ibge" / f"municipios_{hoje}.json"
    baixar("IBGE localidades/municipios", URL, destino, ano_ref=hoje[:4])

    dados = json.loads(destino.read_text(encoding="utf-8"))
    df = pd.DataFrame(
        {
            "cod_ibge_7": [str(m["id"]).zfill(7) for m in dados],
            "municipio": [m["nome"] for m in dados],
            "uf": [_uf(m)["sigla"] for m in dados],
            "regiao": [_uf(m)["regiao"]["nome"] for m in dados],
        }
    )
    df.insert(1, "cod_ibge_6", df["cod_ibge_7"].str[:6])
    df["ano_ref"] = int(hoje[:4])

    assert len(df) == N_MUNICIPIOS, f"esperado {N_MUNICIPIOS}, veio {len(df)}"
    assert df["cod_ibge_7"].is_unique and df["cod_ibge_6"].is_unique
    assert df["cod_ibge_7"].str.fullmatch(r"\d{7}").all()

    INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(INTERIM / "ref_municipios.parquet", index=False)
    dicionario.salvar(df, DICIONARIO, INTERIM / "ref_municipios.parquet")
    return df


DICIONARIO = {
    "cod_ibge_7": COMUNS["cod_ibge_7"],
    "cod_ibge_6": Col("Código IBGE de 6 dígitos (sem o dígito verificador), usado pelo DataSUS",
                      "código", "calculado", FONTE_IBGE),
    "municipio": COMUNS["municipio"],
    "uf": Col("Sigla da UF (de microrregiao; para municípios sem microrregião, de regiao-imediata)",
              "texto", "publicado", FONTE_IBGE),
    "regiao": Col("Grande região (Norte, Nordeste, Centro-Oeste, Sudeste, Sul)", "texto",
                  "publicado", FONTE_IBGE),
    "ano_ref": Col("Ano em que a lista de municípios foi baixada", "ano", "referencia", FONTE_IBGE),
}


if __name__ == "__main__":
    out = run()
    print(out.shape)
    print(out.groupby("regiao").size())
