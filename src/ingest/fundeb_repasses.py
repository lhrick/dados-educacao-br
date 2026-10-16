"""Fase 1.3b — Fundeb: repasses EFETIVOS por ente e mês (Tesouro Nacional).

API de Transferências Constitucionais do Tesouro (apiapex.tesouro.gov.br/aria), endpoints
/por_estado_municipio (municípios, paginado, traz CO_IBGE) e /por_estados (governos
estaduais). Transferências 10 (FUNDEB) e 14 (AJUSTE FUNDEB), detalhadas por componente.
Caminhos confirmados no código do pacote R `tesouror` 0.3.1 (CRAN).

Componentes (TRANSFERENCIA): "FUNDEB - <FPM|FPE|ICMS|IPVA|ITCMD|ITR|IPI-EXP>" = contribuição
de estados e municípios; "FUNDEB - COUN VAAF|VAAT|VAAR" = complementação da União;
"FUNDEB - FUNDEB - FTI" = fomento ao tempo integral (ETI, também da complementação);
"AJUSTE FUNDEB - ..." = ajustes de exercícios anteriores pagos no ano.

Base de caixa: ano = ano do repasse (jan/2025 inclui a 13ª parcela da complementação de 2024).

Saída: data/interim/fundeb_repasses_<ano>.parquet — ente × mês × componente.
"""
from __future__ import annotations

import argparse
import json
import time

import pandas as pd
import requests

from src import dicionario
from src.dicionario import Col
from src.manifest import HEADERS, INTERIM, RAW, ca_bundle, registrar

BASE = "https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais/custom"
TRANSF = "10:14"
FONTE = "Tesouro Nacional — API Transferências Constitucionais (FUNDEB e AJUSTE FUNDEB)"


def _get(url: str, params: dict | None = None, tentativas: int = 4) -> dict:
    for t in range(1, tentativas + 1):
        try:
            r = requests.get(url, params=params, timeout=180, verify=ca_bundle(), headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if t == tentativas:
                raise
            time.sleep(5 * t)


def _baixar_paginado(endpoint: str, params: dict, destino) -> list[dict]:
    """Pagina até uma página vir incompleta e grava a lista completa como JSON bruto.

    A API devolve `next` mesmo na última página — não dá para usá-lo como critério de parada.
    """
    if destino.exists():
        return json.loads(destino.read_text(encoding="utf-8"))
    regs, page, tam = [], 1, 5000
    while True:
        d = _get(f"{BASE}/{endpoint}", {**params, "page": page, "pageSize": tam})
        regs.extend(d["registros"])
        if len(d["registros"]) < int(d.get("pageSize", tam)):
            break
        page += 1
        assert page < 500, f"paginação sem fim em {endpoint} {params}"
        time.sleep(0.5)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(regs, ensure_ascii=False), encoding="utf-8")
    q = "&".join(f"{k}={v}" for k, v in params.items())
    registrar(FONTE, f"{BASE}/{endpoint}?{q}", destino, params["p_ano"])
    return regs


def run(ano: int) -> pd.DataFrame:
    pasta = RAW / "tesouro" / f"fundeb_{ano}"
    estados = _get(f"{BASE}/estados")["registros"]
    p = {"p_ano": ano, "p_transferencia": TRANSF, "p_sn_detalhar": "sim"}

    partes = []
    for e in estados:
        regs = _baixar_paginado("por_estado_municipio", {"p_estado": e["codigo"], **p},
                                pasta / f"municipios_estado{e['codigo']:02d}.json")
        df = pd.DataFrame(regs)
        if df.empty:  # DF não tem municípios; entra pelo endpoint dos governos estaduais
            print(f"{e['nome']}: sem municípios")
            continue
        partes.append(pd.DataFrame({
            "cod_ibge": df.CO_IBGE.astype(str).str.zfill(7), "uf": df.UF, "tipo_ente": "municipio",
            "mes": df.MES.astype(int), "transferencia": df.TRANSFERENCIA, "valor": df.VALOR.astype(float)}))
        print(f"{e['nome']}: {len(df):,} linhas")

    regs = _baixar_paginado("por_estados", p, pasta / "governos_estaduais.json")
    df = pd.DataFrame(regs)
    ref = pd.read_parquet(INTERIM / "ref_municipios.parquet")
    uf_cod = ref.assign(c=ref.cod_ibge_7.str[:2]).drop_duplicates("uf").set_index("uf").c
    partes.append(pd.DataFrame({
        "cod_ibge": df.uf.map(uf_cod), "uf": df.uf, "tipo_ente": "estado",
        "mes": df.mes.astype(int), "transferencia": df.transferencia, "valor": df.valor.astype(float)}))

    out = pd.concat(partes, ignore_index=True)
    assert out.cod_ibge.notna().all()
    out["componente"] = out.transferencia.map(_componente)
    assert out.componente.notna().all(), out[out.componente.isna()].transferencia.unique()
    out["ano_ref"] = ano
    out = out.groupby(["cod_ibge", "uf", "tipo_ente", "mes", "transferencia", "componente", "ano_ref"],
                      as_index=False).valor.sum()
    out.to_parquet(INTERIM / f"fundeb_repasses_{ano}.parquet", index=False)
    dicionario.salvar(out, DICIONARIO, INTERIM / f"fundeb_repasses_{ano}.parquet")
    return out


def _componente(t: str) -> str | None:
    if t.startswith("AJUSTE FUNDEB"):
        return "ajuste"
    if t.endswith(("COUN VAAF", "COUN VAAT", "COUN VAAR")):
        return "compl_" + t[-4:].lower()
    if t.endswith(" FTI"):
        return "fti"
    if t.startswith("FUNDEB - "):
        return "contribuicao"
    return None


DICIONARIO = {
    "cod_ibge": Col("Código IBGE do ente: 7 dígitos = município (CO_IBGE da API); 2 dígitos = governo "
                    "estadual (derivado da UF)", "código", "chave", FONTE),
    "uf": Col("Sigla da UF", "texto", "publicado", FONTE),
    "tipo_ente": Col("municipio (endpoint /por_estado_municipio) ou estado (/por_estados)", "categoria",
                     "referencia", FONTE),
    "mes": Col("Mês do repasse", "mês (1–12)", "publicado", FONTE),
    "transferencia": Col("Componente como publicado (TRANSFERENCIA), ex.: 'FUNDEB - ICMS', "
                         "'FUNDEB - COUN VAAT', 'FUNDEB - FUNDEB - FTI', 'AJUSTE FUNDEB - FPM'",
                         "texto", "publicado", FONTE),
    "componente": Col("Agrupamento: contribuicao (impostos de estados/municípios), compl_vaaf/compl_vaat/"
                      "compl_vaar (complementação da União), fti (fomento tempo integral = ETI), ajuste "
                      "(acertos de exercícios anteriores)", "categoria", "calculado", "pipeline"),
    "ano_ref": Col("Ano do repasse (base de caixa)", "ano", "referencia", FONTE),
    "valor": Col("Valor repassado no mês", "R$", "publicado", FONTE),
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2025)
    o = run(ap.parse_args().ano)
    print(o.groupby(["tipo_ente", "componente"]).valor.sum().div(1e9).round(3))
    print("municípios:", o[o.tipo_ente == "municipio"].cod_ibge.nunique(), "| meses:", sorted(o.mes.unique()))
