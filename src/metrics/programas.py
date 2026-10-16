"""Explicação dos programas: o que são, como o dinheiro chega ao município, valor por aluno/escola
e risco de corte. Gera, a partir da MESMA fonte (este módulo + tabelas do pipeline):

- data/processed/programas_explicacao_<ano>.csv  (uma linha por programa, para ir junto com o CSV)
- docs/programas.md                               (versão legível no projeto)

Os números nacionais são calculados das tabelas na hora de gerar — nunca digitados.
"""
from __future__ import annotations

import pandas as pd

from src import dicionario
from src.dicionario import Col
from src.manifest import INTERIM, PROCESSED, ROOT

ANO = 2025


def _br(n: float, casas: int = 0) -> str:
    s = f"{n:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _reais(v: float) -> str:
    return f"R$ {_br(v / 1e9, 2)} bi" if v >= 1e9 else f"R$ {_br(v / 1e6, 1)} mi"


def numeros(ano: int = ANO) -> dict[str, dict[str, str]]:
    d = pd.read_parquet(PROCESSED / f"educacao_municipios_{ano}.parquet")
    pdm = pd.read_parquet(INTERIM / "pe_de_meia_parcelas.parquet")
    pdm = pdm[pdm.periodo_incentivo.str.endswith(str(ano))]
    pnld = pd.read_parquet(INTERIM / f"pnld_uf_{ano}.parquet")
    fu = pd.read_parquet(INTERIM / f"fundeb_municipio_{ano}.parquet")
    eti = pd.read_parquet(INTERIM / f"eti_redes_{ano}.parquet")
    med = lambda s: _br(s.median(), 2)
    return {
        "pe_de_meia": {
            "valor_total": _reais(d.vl_pago_pe_de_meia.sum()),
            "alunos": _br(d.afetados_pe_de_meia.sum()),
            "por_aluno": f"R$ {med(d.vl_por_aluno_pe_de_meia)} (mediana municipal)",
            "municipios": _br((d.afetados_pe_de_meia > 0).sum()),
            "estornos": _br(pdm.qtd_estornos.sum()),
        },
        "pnld": {
            "valor_total": _reais(pnld.vl_pnld.sum()),
            "alunos": _br(d.afetados_pnld.sum()),
            "por_aluno": f"R$ {med(d.vl_pnld_por_aluno_est)} (mediana municipal, estimativa)",
            "municipios": _br((d.afetados_pnld > 0).sum()),
        },
        "fundeb": {
            "valor_total": _reais(fu.vl_receita_mun.sum() + fu.vl_receita_est.sum()),
            "uniao": _reais(fu.vl_compl_uniao_mun.sum() + fu.vl_compl_uniao_est.sum()),
            "alunos": _br(d.afetados_fundeb_complementacao.sum()),
            "por_aluno": f"R$ {med(d.vl_fundeb_por_aluno_rede_municipal)} (mediana, rede municipal)",
            "municipios_uniao": _br((d.vl_fundeb_uniao_rede_municipal.fillna(0) > 0).sum()),
            "municipios_vaar": _br(d.risco_perda_vaar.sum()),
            "por_escola": f"R$ {med(d.vl_fundeb_media_por_escola_rede_municipal)} (mediana municipal da média por escola municipal)",
        },
        "eti": {
            "valor_total": _reais(eti.vl_fomento_eti.sum()),
            "alunos": _br(eti.qtd_matriculas_eti.sum()),
            "por_aluno": f"R$ {_br(eti.vl_fomento_por_matricula_eti.median(), 2)} por matrícula (mediana das redes)",
            "municipios": _br((d.vl_fomento_eti_rede_municipal.fillna(0) > 0).sum()),
            "por_escola": f"R$ {med(d.vl_eti_media_por_escola_rede_municipal)} (mediana municipal da média por escola com tempo integral)",
            "sem_escola": _br(((d.vl_fomento_eti_rede_municipal.fillna(0) > 0)
                               & (d.qtd_escolas_eti_rede_municipal == 0)).sum()),
        },
        "alunos_rede_publica": {"total": _br(d.qtd_alunos_rede_publica.sum())},
    }


def programas(ano: int = ANO) -> list[dict[str, str]]:
    n = numeros(ano)
    p, l, f, e = n["pe_de_meia"], n["pnld"], n["fundeb"], n["eti"]
    return [
        {
            "programa": "Pé-de-Meia",
            "o_que_e": "Incentivo financeiro-educacional, na modalidade poupança, para estudantes do ensino médio "
                       "público de famílias inscritas no CadÚnico.",
            "como_chega_ao_municipio": "Direto na conta do estudante (não passa pela prefeitura nem pela "
                                       "secretaria estadual). Parcelas: Matrícula R$ 200 por ano; Frequência "
                                       "R$ 200 por mês (R$ 225 na maior parte das parcelas de EJA); Conclusão "
                                       "R$ 1.000 por ano concluído, depositada em poupança; Enem R$ 200.",
            "valor_por_aluno": f"vl_por_aluno_pe_de_meia = valor pago no ano letivo ÷ beneficiários. {p['por_aluno']}.",
            "valor_por_escola": "Não disponível: a fonte (CGU) identifica só o município do estudante, não a escola.",
            "alunos_afetados_corte": f"afetados_pe_de_meia = beneficiários do ano letivo (uma parcela de "
                                     f"Matrícula por estudante). Brasil: {p['alunos']} estudantes em "
                                     f"{p['municipios']} municípios.",
            "risco_corte": "Programa federal criado por lei; o pagamento depende de dotação orçamentária anual. "
                           "Interrupção afeta diretamente a renda dos estudantes beneficiários.",
            "natureza_dos_numeros": "Calculado a partir de pagamentos publicados (valores líquidos de estornos).",
            "valor_total_brasil": p["valor_total"],
            "limitacoes": "Beneficiários = parcelas de Matrícula (a fonte não permite identificar estudantes "
                          "menores de idade). 'Conclusão' é poupança, não dinheiro sacável no ano. "
                          f"{p['estornos']} estornos de Conclusão no ano, já descontados. Razão beneficiários/"
                          "matrículas > 1 em alguns municípios: conferir antes de publicar.",
            "base_legal": "Lei nº 14.818/2024; Decreto nº 11.901/2024.",
            "fonte_dados": "CGU — Portal da Transparência, arquivos mensais do Pé-de-Meia.",
            "colunas_no_csv": "qtd_beneficiarios_pe_de_meia, afetados_pe_de_meia, vl_pago_pe_de_meia, "
                              "vl_por_aluno_pe_de_meia, vl_conclusao_pe_de_meia, razao_pe_de_meia_censo, "
                              "flag_pe_de_meia_acima_censo, txt_pe_de_meia, txt_afetados_pe_de_meia",
        },
        {
            "programa": "PNLD — Programa Nacional do Livro e do Material Didático",
            "o_que_e": "Compra centralizada de livros didáticos e literários para alunos e professores das "
                       "escolas públicas da educação básica.",
            "como_chega_ao_municipio": "Em livros, não em dinheiro: o FNDE compra das editoras e entrega "
                                      "direto nas escolas. O valor é o custo de aquisição.",
            "valor_por_aluno": f"vl_pnld_por_aluno_est = valor estimado ÷ alunos atendidos. {l['por_aluno']}.",
            "valor_por_escola": "Não disponível em base pública: o FNDE publica só por UF; a consulta por escola "
                                "é individual (pedido via LAI pendente).",
            "alunos_afetados_corte": f"afetados_pnld = alunos atendidos (um objeto por etapa, mesma regra do "
                                     f"total publicado pelo FNDE). Brasil: {l['alunos']} alunos.",
            "risco_corte": "Interrupção da compra deixa as escolas sem material didático no ciclo seguinte; "
                           "o efeito aparece no início do ano letivo.",
            "natureza_dos_numeros": "ESTIMATIVA no nível municipal: total da UF rateado pelas matrículas "
                                    "públicas da etapa no Censo.",
            "valor_total_brasil": l["valor_total"],
            "limitacoes": "Rateio supõe adesão de todas as redes públicas da UF; em MT (anos finais e ensino "
                          "médio) e PB (ensino médio) a cobertura é baixa — flag_pnld_cobertura_baixa_uf. "
                          "Não gerar texto de PNLD por município.",
            "base_legal": "Decreto nº 9.099/2017.",
            "fonte_dados": "FNDE — PNLD, Dados estatísticos por UF (PNLD 2025).",
            "colunas_no_csv": "afetados_pnld, vl_pnld_total_est, vl_pnld_por_aluno_est, flag_pnld_cobertura_baixa_uf",
        },
        {
            "programa": "Fundeb",
            "o_que_e": "Fundo constitucional e permanente que redistribui impostos de estados e municípios "
                       "dentro de cada UF, por matrícula, com complementação da União (VAAF, VAAT e VAAR).",
            "como_chega_ao_municipio": "Repasse automático à conta do Fundeb de cada rede (prefeitura e governo "
                                       "estadual), em parcelas ao longo do ano. A contribuição vem de FPM, FPE, "
                                       "ICMS, IPVA, ITCMD, ITR e IPI-Exportação; a União complementa as redes "
                                       "abaixo dos valores mínimos (VAAF, VAAT) e por resultados (VAAR).",
            "valor_por_aluno": f"vl_fundeb_por_aluno_rede_municipal = receita do ano ÷ matrículas da rede no "
                               f"Censo (sem ponderação). {f['por_aluno']}.",
            "valor_por_escola": f"Não há valor por escola publicado (o dinheiro vai para a rede). Calculamos a "
                                f"MÉDIA: vl_fundeb_media_por_escola_rede_municipal = Fundeb da rede municipal ÷ "
                                f"escolas municipais com matrícula. {f['por_escola']}.",
            "alunos_afetados_corte": f"afetados_fundeb_complementacao = matrículas das redes que recebem "
                                     f"complementação da União. Brasil: {f['alunos']} matrículas.",
            "risco_corte": f"Não há 'corte total' (EC 108/2020). O risco é a complementação da União "
                           f"({f['uniao']} em 2025) — perda_fundeb_sem_uniao — e a perda de VAAT/VAAR por "
                           f"inabilitação (dados não enviados ao SIOPE/SICONFI) ou condicionalidades. "
                           f"{f['municipios_vaar']} redes municipais receberam VAAR em 2025 (risco_perda_vaar).",
            "natureza_dos_numeros": "Rede municipal: repasses efetivos publicados. Rede estadual por município: "
                                    "ESTIMATIVA (rateio pelas matrículas estaduais).",
            "valor_total_brasil": f["valor_total"],
            "limitacoes": "Base de caixa (janeiro inclui a última parcela do ano anterior). Valor por aluno usa "
                          "matrículas sem ponderação. O fomento ETI (FTI) é excluído do total para não ser "
                          "somado duas vezes.",
            "base_legal": "Constituição, art. 212-A (EC 108/2020); Lei nº 14.113/2020.",
            "fonte_dados": "Tesouro Nacional — API de Transferências Constitucionais (repasses 2025).",
            "colunas_no_csv": "vl_fundeb_rede_municipal, vl_fundeb_uniao_rede_municipal, pct_uniao_rede_municipal, "
                              "vl_fundeb_por_aluno_rede_municipal, vl_fundeb_rede_estadual_est, "
                              "vl_fundeb_uniao_rede_estadual_est, afetados_fundeb_complementacao, "
                              "perda_fundeb_sem_uniao, risco_perda_vaar, recebe_vaaf/vaat/vaar_rede_municipal, "
                              "qtd_escolas_rede_municipal, vl_fundeb_media_por_escola_rede_municipal, "
                              "txt_fundeb_uniao, txt_afetados_fundeb",
        },
        {
            "programa": "Escola em Tempo Integral (fomento)",
            "o_que_e": "Fomento federal por matrícula em tempo integral criada pelas redes (diferença entre os "
                       "Censos de 2022 e 2024).",
            "como_chega_ao_municipio": "Repasse do FNDE à rede de ensino (prefeitura ou governo estadual) em "
                                       "4 parcelas (out/2025 a jan/2026). Desde a EC 135/2024 o recurso sai da "
                                       "complementação da União ao Fundeb.",
            "valor_por_aluno": f"Valor por matrícula variável por rede (critérios da Portaria MEC 1.495/2023). "
                               f"{e['por_aluno']}.",
            "valor_por_escola": f"Não há valor por escola publicado (o fomento vai para a rede). Calculamos a "
                                f"MÉDIA: vl_eti_media_por_escola_rede_municipal = fomento da rede municipal ÷ "
                                f"escolas municipais com matrícula em tempo integral (vazio onde o Censo 2024 não "
                                f"tem escola integral, {e['sem_escola']} municípios). {e['por_escola']}.",
            "alunos_afetados_corte": f"afetados_eti = matrículas em tempo integral fomentadas (rede municipal "
                                     f"publicada + rede estadual rateada). Brasil: {e['alunos']} matrículas.",
            "risco_corte": "Sem o fomento, as redes custeiam com recursos próprios as matrículas integrais já "
                           "criadas. A partir de 2026 a criação de matrículas integrais passa a ser obrigação de "
                           "aplicação do próprio Fundeb (Resolução CIF nº 23/2026).",
            "natureza_dos_numeros": "Rede municipal: publicado (anexos das portarias). Rede estadual por "
                                    "município: ESTIMATIVA.",
            "valor_total_brasil": e["valor_total"],
            "limitacoes": "Não somar com o Fundeb do mesmo ano: é parte da complementação da União (no Tesouro "
                          "aparece como FTI). Redes sem política de tempo integral registrada tiveram desconto "
                          "de 45%.",
            "base_legal": "Lei nº 14.640/2023; EC 135/2024; Portarias MEC nº 586, 605 e 823/2025.",
            "fonte_dados": "DOU — Portaria MEC 605/2025 (matrículas) e 823/2025 (valores vigentes).",
            "colunas_no_csv": "afetados_eti, qtd_matriculas_eti_rede_municipal, vl_fomento_eti_rede_municipal, "
                              "vl_fomento_eti_rede_estadual_est, registrou_politica_eti_rede_municipal, "
                              "qtd_escolas_eti_rede_municipal, vl_eti_media_por_escola_rede_municipal, "
                              "txt_eti, txt_afetados_eti",
        },
    ]


_F = "src/metrics/programas.py (texto verificado nas fontes; números das tabelas do pipeline)"
DICIONARIO = {
    "programa": Col("Nome do programa", "texto", "chave", _F),
    "ano_ref": Col("Ano de referência dos números", "ano", "referencia", _F),
    "o_que_e": Col("Descrição curta do programa", "texto", "referencia", _F),
    "como_chega_ao_municipio": Col("Forma como o recurso chega (conta do estudante, rede, livros na escola)",
                                   "texto", "referencia", _F),
    "valor_por_aluno": Col("Definição da coluna de valor por aluno e mediana nacional", "texto", "calculado", _F),
    "valor_por_escola": Col("Disponibilidade de valor por escola e motivo", "texto", "referencia", _F),
    "alunos_afetados_corte": Col("Definição da coluna afetados_* e total nacional", "texto", "calculado", _F),
    "risco_corte": Col("Como um corte/interrupção afetaria o município", "texto", "referencia", _F),
    "natureza_dos_numeros": Col("Se os números municipais são publicados ou estimados", "texto", "referencia", _F),
    "valor_total_brasil": Col("Valor total do programa no Brasil no ano", "texto (R$)", "calculado", _F),
    "limitacoes": Col("Limitações e cuidados para publicação", "texto", "referencia", _F),
    "base_legal": Col("Normas que criam/regulam o programa", "texto", "referencia", _F),
    "fonte_dados": Col("Fonte oficial dos dados usados", "texto", "referencia", _F),
    "colunas_no_csv": Col("Colunas do educacao_municipios_<ano>.csv relativas ao programa", "texto",
                          "referencia", _F),
}


def run(ano: int = ANO) -> pd.DataFrame:
    progs = programas(ano)
    df = pd.DataFrame(progs)
    df.insert(1, "ano_ref", ano)
    destino = PROCESSED / f"programas_explicacao_{ano}.csv"
    df.to_csv(destino, sep=";", index=False, encoding="utf-8-sig")
    dicionario.salvar(df, DICIONARIO, destino)
    _md(progs, numeros(ano), ano)
    return df


def _md(progs: list[dict[str, str]], n: dict, ano: int) -> None:
    rot = {
        "o_que_e": "O que é", "como_chega_ao_municipio": "Como chega ao município",
        "valor_por_aluno": "Valor por aluno", "valor_por_escola": "Valor por escola",
        "alunos_afetados_corte": "Alunos afetados por corte", "risco_corte": "Risco de corte/interrupção",
        "natureza_dos_numeros": "Natureza dos números", "limitacoes": "Limitações",
        "base_legal": "Base legal", "fonte_dados": "Fonte dos dados", "colunas_no_csv": "Colunas no CSV",
    }
    L = [
        f"# Programas federais de educação por município — {ano}", "",
        "> Gerado por `src/metrics/programas.py` a partir das tabelas do pipeline. Não editar à mão: "
        "rode `.venv/bin/python -m src.metrics.programas`.", "",
        f"Arquivo de dados: `data/processed/educacao_municipios_{ano}.csv` (uma linha por município) e "
        f"`educacao_municipios_{ano}_dicionario.csv` (descrição de cada coluna, com fonte e tipo).", "",
        "## Resumo — Brasil", "",
        "| Programa | Como chega | Valor no ano | Alunos afetados por corte | Por aluno | Por escola |",
        "|---|---|---:|---:|---|---|",
    ]
    curto = {"Pé-de-Meia": "conta do estudante", "Fundeb": "conta do Fundeb da rede",
             "Escola em Tempo Integral (fomento)": "repasse à rede"}
    for p, k in zip(progs, ["pe_de_meia", "pnld", "fundeb", "eti"]):
        como = curto.get(p["programa"], "livros entregues na escola")
        por_escola = n[k].get("por_escola", "não disponível")
        L.append(f"| {p['programa']} | {como} | {p['valor_total_brasil']} | {n[k]['alunos']} | "
                 f"{n[k]['por_aluno']} | {por_escola} |")
    L += [
        "", f"**Nunca somar os alunos afetados entre programas** — o mesmo estudante pode estar em vários. "
            f"Total de alunos distintos nas redes públicas (Censo 2024): **{n['alunos_rede_publica']['total']}**.",
        "", "**Por escola:** nenhuma das fontes publica valores por escola (Pé-de-Meia só tem município; PNLD só "
            "UF; Fundeb e ETI são pagos à rede de ensino). Para Fundeb e ETI há uma **média por escola** (valor da "
            "rede municipal ÷ escolas da rede) — é uma média, não o que cada escola recebe.", "",
        "**Risco de corte:** cada programa tem sua coluna `afetados_*` (número de alunos/matrículas por cidade). "
        "Frases prontas: `txt_afetados_pe_de_meia`, `txt_afetados_fundeb`, `txt_afetados_eti` (só valores "
        "publicados/calculados — não há frase de PNLD, que é estimativa).", "",
        "**Tipos de número** (coluna `tipo` do dicionário): `publicado` = valor oficial; `calculado` = regra "
        "determinística sobre valores oficiais; `estimativa` = rateio/aproximação nossa — não apresentar como "
        "número oficial.", "",
    ]
    for p in progs:
        L += [f"## {p['programa']}", ""]
        L += [f"- **{rot[k]}:** {p[k]}" for k in rot]
        L += [f"- **Valor total no Brasil ({ano}):** {p['valor_total_brasil']}", ""]
    (ROOT / "docs" / "programas.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    out = run()
    print(out[["programa", "valor_total_brasil"]].to_string(index=False))
