"""Dicionários de dados: um por tabela, declarado no módulo que gera a tabela.

Cada saída ganha `<tabela>_dicionario.csv` ao lado. O dicionário consolidado da Fase 4
é montado juntando estes (nunca escrito à mão).

Tipos de coluna:
- chave       identificador (cod_ibge_7, co_entidade...)
- referencia  atributo descritivo (nome, UF, ano de referência...)
- publicado   valor como veio da fonte oficial (só renomeado/convertido)
- calculado   derivado de valores publicados por regra determinística
- estimativa  rateio/aproximação nossa — NÃO é número oficial
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TIPOS = {"chave", "referencia", "publicado", "calculado", "estimativa"}


@dataclass(frozen=True)
class Col:
    descricao: str
    unidade: str
    tipo: str
    fonte: str

    def __post_init__(self):
        assert self.tipo in TIPOS, f"tipo inválido: {self.tipo}"


# Colunas que se repetem entre tabelas.
FONTE_IBGE = "IBGE — API de localidades (servicodados.ibge.gov.br)"
COMUNS = {
    "cod_ibge_7": Col("Código IBGE do município (7 dígitos, texto, zero à esquerda preservado)",
                      "código", "chave", FONTE_IBGE),
    "municipio": Col("Nome do município", "texto", "referencia", FONTE_IBGE),
    "uf": Col("Sigla da unidade da federação", "texto", "referencia", FONTE_IBGE),
    "ano_ref": Col("Ano de referência dos valores da tabela", "ano", "referencia", "pipeline"),
    "ano_ref_censo": Col("Ano do Censo Escolar usado nas matrículas desta tabela", "ano",
                         "referencia", "pipeline"),
}


def validar(df: pd.DataFrame, dicionario: dict[str, Col], tabela: str) -> None:
    faltam = [c for c in df.columns if c not in dicionario]
    sobram = [c for c in dicionario if c not in df.columns]
    assert not faltam and not sobram, (
        f"dicionário de '{tabela}' fora de sincronia — sem descrição: {faltam}; "
        f"descritas mas inexistentes: {sobram}")


def como_tabela(df: pd.DataFrame, dicionario: dict[str, Col], tabela: str) -> pd.DataFrame:
    validar(df, dicionario, tabela)
    return pd.DataFrame([
        {"tabela": tabela, "coluna": c, "tipo_dado": str(df[c].dtype), **vars(dicionario[c])}
        for c in df.columns
    ])


def salvar(df: pd.DataFrame, dicionario: dict[str, Col], arquivo_dados: Path) -> Path:
    """Valida e grava `<stem>_dicionario.csv` ao lado do arquivo de dados."""
    tabela = arquivo_dados.stem
    destino = arquivo_dados.with_name(f"{tabela}_dicionario.csv")
    como_tabela(df, dicionario, tabela).to_csv(destino, sep=";", index=False, encoding="utf-8-sig")
    return destino
