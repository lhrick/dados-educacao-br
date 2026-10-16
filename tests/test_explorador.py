"""Configs do explorador interativo apontam para colunas reais e respeitam as regras de publicação."""
import json

import pandas as pd
import pytest

from src.manifest import PROCESSED
from src.viz import explorador

CONFIGS = sorted(explorador.CONFIGS.glob("*.json"))
MALHA_VAZIA = {"largura": 1, "altura": 1, "municipios": {}, "ufs": []}


def _carregar(cfg_path):
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = PROCESSED / config["fonte_tabela"]
    if not base.with_suffix(".parquet").exists():
        pytest.skip("tabela final ainda não gerada")
    df = pd.read_parquet(base.with_suffix(".parquet"))
    dic = pd.read_csv(f"{base}_dicionario.csv", sep=";", dtype=str, encoding="utf-8-sig")
    return config, df, dic


@pytest.mark.parametrize("cfg_path", CONFIGS, ids=lambda p: p.stem)
def test_config_monta_payload(cfg_path):
    config, df, dic = _carregar(cfg_path)
    payload = explorador.montar_payload(df, dic, config, MALHA_VAZIA)
    assert len(payload["linhas"]["cod"]) == len(df)
    # toda coluna exibida tem metadado do dicionário (descrição, tipo e fonte)
    for col, meta in payload["metricas"].items():
        assert meta["tipo"], f"{col} sem tipo no dicionário"
    # tudo o que a config referencia está em metricas
    refs = config["ficha"] + config["tabela"] + config.get("tooltip", []) + config.get("resumo", [])
    refs += [m["coluna"] for m in config["mapa"]]
    assert set(refs) <= set(config["metricas"])


@pytest.mark.parametrize("cfg_path", CONFIGS, ids=lambda p: p.stem)
def test_frases_nao_vem_de_estimativa(cfg_path):
    config, df, dic = _carregar(cfg_path)
    tipos = dic.set_index("coluna")["tipo"]
    for col in config.get("textos", []):
        assert tipos[col] != "estimativa", f"{col}: texto pronto não pode vir de estimativa"


def test_coluna_inexistente_falha():
    df = pd.DataFrame({"cod_ibge_7": ["1100015"], "municipio": ["X"], "uf": ["RO"]})
    dic = pd.DataFrame(columns=["coluna", "descricao", "unidade", "tipo", "fonte"])
    config = {"chave": "cod_ibge_7", "nome": "municipio", "uf": "uf", "metricas": {"nao_existe": {}}}
    with pytest.raises(KeyError):
        explorador.montar_payload(df, dic, config, MALHA_VAZIA)


def test_template_tem_marcadores():
    html = explorador.TEMPLATE.read_text(encoding="utf-8")
    assert "__TITULO__" in html and "/*__DADOS__*/{}" in html
