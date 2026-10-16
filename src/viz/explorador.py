"""Explorador interativo por município: template HTML genérico + configuração por programa.

    .venv/bin/python -m src.viz.explorador                 # todas as configs em src/viz/configs/
    .venv/bin/python -m src.viz.explorador pe_de_meia      # só uma

Contrato (reaproveitável em outro projeto):
- tabela com uma linha por município e chave `cod_ibge_7`;
- dicionário de dados (`<tabela>_dicionario.csv`: coluna, descricao, unidade, tipo, fonte);
- config JSON (src/viz/configs/<id>.json) dizendo quais colunas mostrar e como.

O template (src/viz/templates/explorador.html) não conhece nenhum programa: lê tudo do
JSON embutido. A saída é um único HTML, sem dependência externa, que abre offline.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src.manifest import PROCESSED, RAW, ROOT, baixar

AQUI = Path(__file__).parent
TEMPLATE = AQUI / "templates" / "explorador.html"
CONFIGS = AQUI / "configs"
SAIDA = ROOT / "docs" / "explorador"

URL_MALHA = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio"
)
CRS_BR = "EPSG:5880"  # SIRGAS 2000 / Brazil Polyconic
TOLERANCIA = 4000    # simplificação da malha (shapely.coverage_simplify; preserva bordas compartilhadas)
UNIDADE_M = 500      # 1 unidade do SVG = 500 m


# ---------------------------------------------------------------- malha → caminhos SVG
def malha_municipios() -> gpd.GeoDataFrame:
    """Malha municipal do IBGE (API de malhas v3, qualidade mínima), registrada no manifest."""
    p = baixar("IBGE malhas v3 (municipios, qualidade minima)", URL_MALHA,
               RAW / "ibge" / "malha_municipios_minima.geojson", ano_ref=2026)
    return gpd.read_file(p).to_crs(CRS_BR)


def _anel(coords: np.ndarray) -> str:
    pts = np.round(coords[:, :2] / UNIDADE_M).astype(int)
    d = np.diff(pts, axis=0)
    d = d[(d != 0).any(axis=1)]
    if len(d) < 2:
        return ""
    return f"M{pts[0, 0]} {pts[0, 1]}l" + " ".join(f"{x} {y}" for x, y in d) + "z"


def _caminho(geom) -> str:
    partes = []
    for poly in getattr(geom, "geoms", [geom]):
        for anel in [poly.exterior, *poly.interiors]:
            partes.append(_anel(np.asarray(anel.coords)))
    return "".join(partes)


def malha_svg(gmun: gpd.GeoDataFrame) -> dict:
    """Projeta (CRS_BR), simplifica e converte para caminhos SVG com y invertido.

    A simplificação é feita sobre a cobertura inteira, então vizinhos continuam com a mesma
    borda (sem frestas). As divisas estaduais saem da união dos municípios já simplificados.
    """
    minx, miny, maxx, maxy = gmun.total_bounds
    simpl = gpd.GeoSeries(shapely.coverage_simplify(gmun.geometry.values, TOLERANCIA), crs=gmun.crs)
    mun = simpl.affine_transform([1, 0, 0, -1, -minx, maxy])  # origem no canto superior esquerdo
    ufs = mun.groupby(gmun["codarea"].str[:2].to_numpy()).agg(shapely.union_all)
    return {
        "largura": int(np.ceil((maxx - minx) / UNIDADE_M)),
        "altura": int(np.ceil((maxy - miny) / UNIDADE_M)),
        "municipios": {cod: _caminho(geo) for cod, geo in zip(gmun["codarea"], mun)},
        "ufs": [_caminho(geo) for geo in ufs],
    }


# ---------------------------------------------------------------- dados
def _valor(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return round(float(v), 4)
    return v


def montar_payload(df: pd.DataFrame, dic: pd.DataFrame, config: dict, malha: dict) -> dict:
    chave, nome, uf = config["chave"], config["nome"], config["uf"]
    de_graficos = [g[k] for g in config.get("graficos", []) for k in ("coluna", "x", "y", "destaque") if k in g]
    de_graficos += [c for g in config.get("graficos", []) for c in g.get("extra", [])]
    usadas = list(dict.fromkeys(
        list(config["metricas"]) + de_graficos
        + [a["coluna"] for a in config.get("alertas", [])] + config.get("textos", [])
    ))
    sem_meta = [c for c in de_graficos + config.get("resumo", []) if c not in config["metricas"]]
    if sem_meta:
        raise KeyError(f"colunas usadas em graficos/resumo precisam estar em config['metricas']: {sem_meta}")
    faltando = [c for c in usadas if c not in df.columns]
    if faltando:
        raise KeyError(f"colunas da config ausentes na tabela: {faltando}")

    dic = dic.set_index("coluna")
    metricas = {}
    for col in usadas:
        meta = dic.loc[col] if col in dic.index else None
        metricas[col] = {
            "descricao": None if meta is None else meta["descricao"],
            "unidade": None if meta is None else meta["unidade"],
            "tipo": None if meta is None else meta["tipo"],
            "fonte": None if meta is None else meta["fonte"],
            **config["metricas"].get(col, {}),
        }

    df = df.sort_values(chave)
    return {
        "config": {k: v for k, v in config.items() if k != "metricas"},
        "metricas": metricas,
        "linhas": {
            "cod": df[chave].tolist(),
            "nome": df[nome].tolist(),
            "uf": df[uf].tolist(),
            "valores": {c: [_valor(v) for v in df[c].tolist()] for c in usadas},
        },
        "malha": malha,
        "gerado_em": date.today().isoformat(),
    }


def renderizar(payload: dict, saida: Path) -> None:
    dados = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__TITULO__", payload["config"]["titulo"]).replace("/*__DADOS__*/{}", dados)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    print(f"  {saida.relative_to(ROOT)} ({saida.stat().st_size / 1e6:.1f} MB)")


def gerar(id_config: str, malha: dict) -> None:
    config = json.loads((CONFIGS / f"{id_config}.json").read_text(encoding="utf-8"))
    base = PROCESSED / config["fonte_tabela"]
    df = pd.read_parquet(base.with_suffix(".parquet"))
    dic = pd.read_csv(f"{base}_dicionario.csv", sep=";", dtype=str, encoding="utf-8-sig")
    renderizar(montar_payload(df, dic, config, malha), SAIDA / f"{id_config}.html")


def run(ids: list[str] | None = None) -> None:
    ids = ids or sorted(p.stem for p in CONFIGS.glob("*.json"))
    malha = malha_svg(malha_municipios())
    print(f"Exploradores em {SAIDA.relative_to(ROOT)}/:")
    for i in ids:
        gerar(i, malha)


if __name__ == "__main__":
    run(sys.argv[1:] or None)
