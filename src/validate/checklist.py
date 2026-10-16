"""Checklist de validação do CLAUDE.md — rodar antes de entregar qualquer CSV.

Gera data/processed/educacao_municipios_<ano>_validacao.md. Status por item:
OK (conferido), ATENÇÃO (passa, mas há casos a revisar), FALHA (bloqueia entrega),
SEM REFERÊNCIA (não há total oficial publicado para conferir — dito explicitamente).
"""
from __future__ import annotations

import re
import sys

import pandas as pd

from src.ingest.eti import TOTAL_PORTARIA_586
from src.ingest.ibge import N_MUNICIPIOS
from src.manifest import INTERIM, MANIFEST, PROCESSED, ROOT, sha256

ANO = 2025
PESSOAIS = re.compile(r"cpf|nis|nome_benef|nome_resp|beneficiario_nome", re.I)
CPF_MASCARADO = re.compile(r"\*{3}\.\d{3}\.\d{3}-\*{2}")


def run(ano: int = ANO) -> list[tuple[str, str, str]]:
    r: list[tuple[str, str, str]] = []
    d = pd.read_parquet(PROCESSED / f"educacao_municipios_{ano}.parquet")

    # 1. Cobertura e unicidade
    ok = len(d) == N_MUNICIPIOS and d.cod_ibge_7.is_unique
    r.append(("OK" if ok else "FALHA", "Municípios presentes e sem duplicata",
              f"{len(d):,} linhas (esperado {N_MUNICIPIOS:,}); duplicatas: {d.cod_ibge_7.duplicated().sum()}"))

    # 2. Totais nacionais vs oficiais
    e = pd.read_parquet(INTERIM / f"eti_redes_{ano}.parquet")
    r.append(("OK" if abs(e.vl_fomento_eti.sum() - TOTAL_PORTARIA_586) < 1 else "FALHA",
              "ETI = Portaria MEC 586/2025", f"R$ {e.vl_fomento_eti.sum():,.2f} vs R$ {TOTAL_PORTARIA_586:,.2f}"))
    p = pd.read_parquet(INTERIM / f"pnld_uf_{ano}.parquet")
    r.append(("OK", "PNLD = linha TOTAL BRASIL da planilha FNDE (conferido no ingest, coluna a coluna)",
              f"R$ {p.vl_pnld.sum():,.2f}; alunos {d.afetados_pnld.sum():,.0f} (rateio arredondado)"))
    fr = pd.read_parquet(INTERIM / f"fundeb_municipio_{ano}.parquet")
    fti = fr.vl_fti_mun.sum()
    eti_ate_dez = e[e.rede == "municipal"][["vl_eti_out_2025", "vl_eti_nov_2025", "vl_eti_dez_2025"]].sum().sum()
    r.append(("OK" if abs(fti - eti_ate_dez) < 1 else "FALHA",
              "Fundeb (Tesouro): FTI repassado = parcelas ETI out–dez (fontes independentes)",
              f"R$ {fti:,.2f} vs R$ {eti_ate_dez:,.2f}"))
    r.append(("SEM REFERÊNCIA", "Fundeb 2025: total de caixa vs total oficial",
              f"Receita R$ {(fr.vl_receita_mun.sum() + fr.vl_receita_est.sum()) / 1e9:,.2f} bi (caixa). Não há total "
              "oficial de caixa por ano para conferir; estimativas de 2025 (Portaria 13/2025) são de competência"))
    r.append(("SEM REFERÊNCIA", "Pé-de-Meia: total nacional vs oficial",
              f"{d.qtd_beneficiarios_pe_de_meia.sum():,} beneficiários (parcelas de matrícula do ano letivo). "
              "Total oficial do MEC para 2025 não conferido"))
    m = pd.read_parquet(INTERIM / "ref_matriculas_municipio.parquet")
    r.append(("OK" if m.qt_mat_bas.sum() == 47_088_922 else "FALHA", "Censo 2024: matrículas da educação básica",
              f"{m.qt_mat_bas.sum():,} (47.088.922 = total do microdado, escolas em atividade)"))

    # 3. Pé-de-Meia vs Censo
    n_acima = int(d.flag_pe_de_meia_acima_censo.sum())
    acima = d[d.flag_pe_de_meia_acima_censo].sort_values("razao_pe_de_meia_censo", ascending=False)
    r.append(("ATENÇÃO" if n_acima else "OK", "Pé-de-Meia / matrículas EM públicas > 1",
              f"{n_acima} municípios (anos diferentes: 2025 × Censo 2024). Maiores: " +
              ", ".join(f"{x.municipio}/{x.uf} {x.razao_pe_de_meia_censo:.2f}" for x in acima.head(5).itertuples())))

    # 4. Zeros por programa
    zeros = {
        "Pé-de-Meia": d.qtd_beneficiarios_pe_de_meia.fillna(0).eq(0),
        "PNLD": d.afetados_pnld.fillna(0).eq(0),
        "Fundeb rede municipal": d.vl_fundeb_rede_municipal.fillna(0).eq(0),
        "ETI rede municipal": d.vl_fomento_eti_rede_municipal.fillna(0).eq(0),
    }
    for prog, z in zeros.items():
        nomes = ", ".join(f"{x.municipio}/{x.uf}" for x in d[z].head(8).itertuples())
        r.append(("ATENÇÃO" if z.sum() else "OK", f"Municípios com zero — {prog}",
                  f"{int(z.sum())}" + (f": {nomes}{' …' if z.sum() > 8 else ''}" if z.sum() else "")))
    # Zeros do Pé-de-Meia: esperados onde não há EM público; nos demais, conferir se não há
    # NENHUMA parcela do ano (zero real) — e não frequência sem matrícula (falha do critério).
    par = pd.read_parquet(INTERIM / "pe_de_meia_parcelas.parquet")
    par = par[par.periodo_incentivo.str[-4:].astype(int) == ano]
    q = par.pivot_table(index="cod_ibge_7", columns="tipo_incentivo", values="qtd_parcelas",
                        aggfunc="sum", fill_value=0)
    freq_sem_mat = ((q.get("Frequência", 0) > 0) & (q.get("Matrícula", 0) == 0)).sum()
    r.append(("OK" if freq_sem_mat == 0 else "FALHA", "Critério de beneficiário (matrícula) cobre quem recebeu frequência",
              f"{int(freq_sem_mat)} municípios com Frequência {ano} > 0 e Matrícula {ano} = 0"))
    sem_em = d[(d.qtd_beneficiarios_pe_de_meia.fillna(0) == 0) & (d.mat_em_publico > 0)]
    reais = sem_em[~sem_em.cod_ibge_7.isin(par.cod_ibge_7)]
    r.append(("OK" if len(sem_em) == len(reais) else "ATENÇÃO",
              "Zeros do Pé-de-Meia com EM público > 0 são zeros reais (nenhuma parcela no ano)",
              f"{len(sem_em)} município(s), {len(reais)} sem nenhuma parcela de {ano}: " +
              ", ".join(f"{x.municipio}/{x.uf} ({x.mat_em_publico} mat. EM)" for x in reais.itertuples())))

    # 5. Dados pessoais
    achados = []
    for pasta in (INTERIM, PROCESSED):
        for f in pasta.glob("*.parquet"):
            df = pd.read_parquet(f)
            cols = [c for c in df.columns if PESSOAIS.search(c)]
            texto = df.select_dtypes(include=["object", "string"])
            cpf = [c for c in texto if texto[c].astype(str).str.contains(CPF_MASCARADO).any()]
            if cols or cpf:
                achados.append(f"{f.name}: {cols + cpf}")
    r.append(("FALHA" if achados else "OK", "Nenhum dado pessoal em interim/ e processed/",
              "; ".join(achados) or "nenhuma coluna de CPF/NIS/nome nem valor com padrão de CPF"))

    # 6. Manifest
    man = pd.read_csv(MANIFEST, dtype=str)
    ruins = [x.arquivo for x in man.itertuples() if not (ROOT / x.arquivo).exists()
             or sha256(ROOT / x.arquivo) != x.hash_sha256]
    r.append(("FALHA" if ruins else "OK", "Manifest com hash de todos os brutos",
              f"{len(man)} arquivos; divergentes/ausentes: {ruins or 'nenhum'}"))

    linhas = [f"# Validação — educacao_municipios_{ano}\n", "| Status | Item | Detalhe |", "|---|---|---|"]
    linhas += [f"| {s} | {i} | {det} |" for s, i, det in r]
    (PROCESSED / f"educacao_municipios_{ano}_validacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return r


if __name__ == "__main__":
    res = run()
    for s, i, det in res:
        print(f"[{s}] {i}\n      {det}")
    sys.exit(1 if any(s == "FALHA" for s, _, _ in res) else 0)
