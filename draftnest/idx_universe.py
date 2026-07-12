"""Daftar seluruh kode emiten IDX (tanpa API key).

Sumber utama: endpoint resmi IDX (GetSecuritiesStock) — dijalankan server-side
di GitHub Actions (jaringan terbuka). Bila gagal, fallback ke daftar yang
di-commit di data/idx_tickers.txt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
FALLBACK_FILE = ROOT / "data" / "idx_tickers.txt"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Endpoint resmi IDX: kembalikan seluruh saham tercatat dalam satu panggilan.
IDX_URL = (
    "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
    "?start=0&length=9999&code=&sector=&board=&language=en-us"
)

_KODE_RE = re.compile(r"^[A-Z]{4}$")


def _dari_idx() -> list[str]:
    import requests

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.idx.co.id/en/market-data/stocks-data/stock-list/",
        "X-Requested-With": "XMLHttpRequest",
    }
    resp = requests.get(IDX_URL, headers=headers, timeout=40)
    resp.raise_for_status()
    data: Any = resp.json()
    rows = data.get("data") or data.get("Data") or []
    kode: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        c = row.get("Code") or row.get("KodeSaham") or row.get("KodeEmiten") or ""
        c = str(c).strip().upper()
        if _KODE_RE.match(c):
            kode.append(c)
    return kode


def _dari_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    kode: list[str] = []
    for baris in path.read_text(encoding="utf-8").splitlines():
        b = baris.split("#", 1)[0].strip().upper()
        if _KODE_RE.match(b):
            kode.append(b)
    return kode


def daftar_emiten(fallback_file: Optional[Path] = None) -> list[str]:
    """Kembalikan daftar kode emiten IDX unik & terurut.

    Coba IDX resmi dulu; bila gagal/kosong, pakai file fallback.
    """
    kode: list[str] = []
    try:
        kode = _dari_idx()
    except Exception:
        kode = []
    if not kode:
        kode = _dari_file(fallback_file or FALLBACK_FILE)
    return sorted(set(kode))
