import math

import pytest

from src.metrics import textos as t


@pytest.mark.parametrize("v,esperado", [
    (950, "R$ 950"), (1_000, "R$ 1 MIL"), (850_000, "R$ 850 MIL"), (999_949, "R$ 999,9 MIL"), (999_999, "R$ 1 MILHÃO"), (999_990_000, "R$ 1 BILHÃO"),
    (1_000_000, "R$ 1 MILHÃO"), (1_960_000, "R$ 2 MILHÕES"), (12_345_678, "R$ 12,3 MILHÕES"),
    (2_500_000_000, "R$ 2,5 BILHÕES"), (1_040_000_000, "R$ 1 BILHÃO"),
])
def test_reais_extenso(v, esperado):
    assert t.reais_extenso(v) == esperado


def test_inteiro_ptbr():
    assert t.inteiro(1234567) == "1.234.567"
    assert t.inteiro(12) == "12"


@pytest.mark.parametrize("vazio", [0, None, math.nan, -5])
def test_sem_texto_para_zero_ou_nulo(vazio):
    assert t.txt_pe_de_meia(vazio, "X", 2025) == ""
    assert t.txt_fundeb_uniao(vazio, 2025) == ""
    assert t.txt_eti(vazio, 100, 2025) == ""
    assert t.txt_eti(10, vazio, 2025) == ""


def test_singular_plural():
    assert t.txt_pe_de_meia(1, "Borá", 2025) == "1 estudante recebeu o Pé-de-Meia em Borá em 2025"
    assert t.txt_pe_de_meia(1234, "Borá", 2025) == "1.234 estudantes receberam o Pé-de-Meia em Borá em 2025"
    assert t.txt_eti(1, 5000, 2025) == "R$ 5 MIL da União pelo fomento a 1 matrícula em tempo integral criada na rede municipal (2025)"


def test_textos_de_risco():
    assert t.txt_afetados_pe_de_meia(734, "Ipixuna") == \
        "Se o Pé-de-Meia for interrompido, 734 estudantes de Ipixuna deixam de receber o incentivo"
    assert t.txt_afetados_fundeb(32292, "X") == \
        "32.292 alunos de X estudam em redes que recebem complementação da União ao Fundeb"
    assert t.txt_afetados_fundeb(1, "X").startswith("1 aluno de X estuda ")
    assert t.txt_afetados_eti(132, "X") == \
        "132 matrículas em tempo integral da rede municipal de X receberam fomento da União"
    for f in (t.txt_afetados_pe_de_meia, t.txt_afetados_fundeb, t.txt_afetados_eti):
        assert f(0, "X") == "" and f(None, "X") == ""
