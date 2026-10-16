"""Cliente da API de dados do Portal da Transparência (CGU).

A chave vem de PORTAL_TRANSPARENCIA_API_KEY (.env) e vai no header
"chave-api-dados". Nunca imprimir a chave.
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

from src.manifest import ROOT, ca_bundle

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/"
HEADER_CHAVE = "chave-api-dados"


def _chave() -> str:
    load_dotenv(ROOT / ".env")
    chave = os.getenv("PORTAL_TRANSPARENCIA_API_KEY", "").strip()
    if not chave:
        raise RuntimeError("PORTAL_TRANSPARENCIA_API_KEY não definida no .env")
    return chave


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({HEADER_CHAVE: _chave(), "Accept": "application/json"})
    s.verify = ca_bundle()
    return s


def get(endpoint: str, params: dict | None = None, s: requests.Session | None = None, timeout: int = 60):
    s = s or sessao()
    r = s.get(BASE_URL + endpoint.lstrip("/"), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()
