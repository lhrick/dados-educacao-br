"""Colunas de texto para templates (WhatsApp / redação / motion), formatação pt-BR.

Regras (CLAUDE.md, Fase 4):
- milhar com ponto, decimal com vírgula;
- valor 0 ou nulo NÃO gera texto (fica vazio, nunca "0 estudantes");
- textos só a partir de valores publicados (nunca de colunas `estimativa`).
"""
from __future__ import annotations

import math

import pandas as pd


def _vazio(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v) or v <= 0


def inteiro(n) -> str:
    """12345 -> '12.345'."""
    return f"{int(round(n)):,}".replace(",", ".")


def reais_extenso(v) -> str:
    """Valor em reais com escala por extenso, 1 casa decimal quando não for inteiro.

    850_000 -> 'R$ 850 MIL'; 12_345_678 -> 'R$ 12,3 MILHÕES'; 1_000_000 -> 'R$ 1 MILHÃO';
    2_500_000_000 -> 'R$ 2,5 BILHÕES'. Abaixo de R$ 1 mil: 'R$ 950'.
    """
    escalas = [(1e9, "BILHÃO", "BILHÕES"), (1e6, "MILHÃO", "MILHÕES"), (1e3, "MIL", "MIL")]
    for i, (lim, sing, plur) in enumerate(escalas):
        if v >= lim:
            x = round(v / lim, 1)
            if x >= 1000 and i > 0:  # 999.999 -> "1 MILHÃO", não "1000 MIL"
                lim, sing, plur = escalas[i - 1]
                x = round(v / lim, 1)
            num = f"{x:.1f}".replace(".", ",").removesuffix(",0")
            return f"R$ {num} {sing if x < 2 else plur}"
    return f"R$ {inteiro(v)}"


def txt_pe_de_meia(n, municipio: str, ano: int) -> str:
    if _vazio(n):
        return ""
    sujeito = "estudante recebeu" if int(round(n)) == 1 else "estudantes receberam"
    return f"{inteiro(n)} {sujeito} o Pé-de-Meia em {municipio} em {ano}"


def txt_fundeb_uniao(v, ano: int) -> str:
    if _vazio(v):
        return ""
    return f"{reais_extenso(v)} do Fundeb da rede municipal vieram da União em {ano}"


def txt_eti(n, v, ano: int) -> str:
    if _vazio(n) or _vazio(v):
        return ""
    mat = "matrícula" if int(round(n)) == 1 else "matrículas"
    # O fomento remunera matrículas JÁ criadas (Censo 2024 − Censo 2022; Portaria MEC 605/2025, art. 2º).
    criada = "criada" if int(round(n)) == 1 else "criadas"
    return (f"{reais_extenso(v)} da União pelo fomento a {inteiro(n)} {mat} em tempo integral "
            f"{criada} na rede municipal ({ano})")


# --- Risco de corte (alunos afetados). Só contagens publicadas/calculadas, nunca estimativas.

def txt_afetados_pe_de_meia(n, municipio: str) -> str:
    if _vazio(n):
        return ""
    quem = "estudante" if int(round(n)) == 1 else "estudantes"
    return f"Se o Pé-de-Meia for interrompido, {inteiro(n)} {quem} de {municipio} deixam de receber o incentivo"


def txt_afetados_fundeb(n, municipio: str) -> str:
    if _vazio(n):
        return ""
    quem = "aluno" if int(round(n)) == 1 else "alunos"
    verbo = "estuda" if int(round(n)) == 1 else "estudam"
    return (f"{inteiro(n)} {quem} de {municipio} {verbo} em redes que recebem complementação da União "
            f"ao Fundeb")


def txt_afetados_eti(n, municipio: str) -> str:
    if _vazio(n):
        return ""
    mat = "matrícula" if int(round(n)) == 1 else "matrículas"
    verbo = "recebeu" if int(round(n)) == 1 else "receberam"
    return (f"{inteiro(n)} {mat} em tempo integral da rede municipal de {municipio} {verbo} fomento "
            f"da União")
