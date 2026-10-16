"""Roda o pipeline de educação de ponta a ponta, na ordem de dependência.

    .venv/bin/python -m src.pipeline            # tudo
    .venv/bin/python -m src.pipeline --de pnld  # a partir de uma etapa

Downloads já presentes em data/raw/ não são refeitos (dados brutos são imutáveis).
Pé-de-Meia: os zips mensais precisam estar em data/raw/cgu/pe_de_meia/ (o servidor da CGU
pode exigir captcha — ver links_pe_de_meia.txt).
"""
from __future__ import annotations

import argparse
import sys
import time

from src.ingest import censo_escolar, eti, fundeb, fundeb_repasses, ibge, pe_de_meia, pnld
from src.transform import consolidar
from src.transform import eti as t_eti
from src.transform import fundeb as t_fundeb_2026
from src.transform import fundeb_repasses as t_fundeb
from src.transform import pe_de_meia as t_pdm
from src.transform import pnld as t_pnld
from src.metrics import programas
from src.validate import checklist

ETAPAS = [
    ("ibge", ibge.run),
    ("censo", censo_escolar.run),
    ("pe_de_meia", pe_de_meia.run),
    ("pe_de_meia_mun", t_pdm.run),
    ("pnld", pnld.run),
    ("pnld_mun", t_pnld.run),
    ("eti", eti.run),
    ("eti_mun", t_eti.run),
    ("fundeb_repasses", lambda: fundeb_repasses.run(2025)),
    ("fundeb_mun", t_fundeb.run),
    ("fundeb_2026_projecao", fundeb.run),
    ("fundeb_2026_projecao_mun", t_fundeb_2026.run),
    ("consolidar", consolidar.run),
    ("programas", programas.run),
    ("validar", checklist.run),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", choices=[n for n, _ in ETAPAS], help="começar desta etapa")
    args = ap.parse_args()
    nomes = [n for n, _ in ETAPAS]
    inicio = nomes.index(args.de) if args.de else 0
    for nome, fn in ETAPAS[inicio:]:
        t = time.time()
        res = fn()
        print(f"[ok] {nome} ({time.time() - t:.0f}s)")
    falhas = [i for s, i, _ in res if s == "FALHA"]
    for f in falhas:
        print(f"[FALHA] {f}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
