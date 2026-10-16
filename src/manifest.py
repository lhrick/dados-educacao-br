"""Registro de proveniência dos downloads em data/raw/_manifest.csv."""
from __future__ import annotations

import csv
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MANIFEST = RAW / "_manifest.csv"
FIELDS = ["fonte", "url", "data_download", "arquivo", "hash_sha256", "ano_ref"]
CERTS = ROOT / "certs"
# Alguns servidores gov.br (ex.: in.gov.br) derrubam conexões com o User-Agent padrão do requests.
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) dados-educacao-br/0.1"}


def ca_bundle() -> str:
    """Bundle de CAs = certifi + intermediários em certs/*.pem.

    Alguns servidores gov.br (ex.: servicodados.ibge.gov.br) não enviam o
    certificado intermediário. Completamos a cadeia em vez de desligar a
    verificação TLS.
    """
    import certifi

    extras = sorted(CERTS.glob("*.pem"))
    if not extras:
        return certifi.where()
    bundle = CERTS / "_bundle.crt"
    partes = [Path(certifi.where()).read_bytes()] + [p.read_bytes() for p in extras]
    conteudo = b"\n".join(partes)
    if not bundle.exists() or bundle.read_bytes() != conteudo:
        bundle.write_bytes(conteudo)
    return str(bundle)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def registrar(fonte: str, url: str, arquivo: Path, ano_ref: str | int) -> None:
    """Acrescenta uma linha ao manifest (cria o arquivo com cabeçalho se preciso)."""
    RAW.mkdir(parents=True, exist_ok=True)
    novo = not MANIFEST.exists()
    with open(MANIFEST, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if novo:
            w.writeheader()
        w.writerow({
            "fonte": fonte,
            "url": url,
            "data_download": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "arquivo": str(arquivo.relative_to(ROOT)),
            "hash_sha256": sha256(arquivo),
            "ano_ref": ano_ref,
        })


def _registrado(arquivo: Path) -> bool:
    if not MANIFEST.exists():
        return False
    rel = str(arquivo.relative_to(ROOT))
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        return any(r["arquivo"] == rel for r in csv.DictReader(f))


def baixar(
    fonte: str, url: str, destino: Path, ano_ref: str | int,
    timeout: int = 600, tentativas: int = 4,
) -> Path:
    """Baixa `url` para `destino` (se ainda não existir) e registra no manifest.

    Dados brutos são imutáveis: se o arquivo já existe, não baixa de novo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        # Arquivo colocado à mão (ex.: fonte com captcha): registra se ainda não está no manifest.
        if not _registrado(destino):
            registrar(fonte, url, destino, ano_ref)
        return destino
    tmp = destino.with_suffix(destino.suffix + ".part")
    for tentativa in range(1, tentativas + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout, verify=ca_bundle(), headers=HEADERS) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            break
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError):
            # Servidores gov.br derrubam conexões de forma intermitente.
            if tentativa == tentativas:
                raise
            time.sleep(5 * tentativa)
    tmp.rename(destino)
    registrar(fonte, url, destino, ano_ref)
    return destino
