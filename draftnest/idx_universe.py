"""Daftar seluruh kode emiten IDX (tanpa API key).

Endpoint resmi IDX diproteksi bot (memblokir IP datacenter termasuk GitHub
Actions), jadi sumber utama adalah CSV "Daftar Saham IDX" yang di-host publik
di GitHub (raw.githubusercontent — terjangkau dari Actions). Union dari beberapa
mirror untuk redundansi, lalu fallback ke data/idx_tickers.txt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
FALLBACK_FILE = ROOT / "data" / "idx_tickers.txt"

USER_AGENT = "Mozilla/5.0 (compatible; DraftnestBot/1.0)"

# Mirror CSV "Daftar Saham IDX" (kolom: No,Kode,Nama Perusahaan,...), di-pin ke
# commit agar stabil. Union ketiganya menutup perbedaan snapshot.
SUMBER_CSV = [
    "https://raw.githubusercontent.com/saranaintegra/saham/74672ec18d66d0ffef4907035f96e143b49ba3af/kodesaham.csv",
    "https://raw.githubusercontent.com/nausya/sahamku/2ffa55e01ed7cc92129658d2bb7a5b40e32fa64d/kodesaham.csv",
    "https://raw.githubusercontent.com/rohmatk/sahamindoo/f14ee634cc47d58809eddb01685a8456c7cf6203/data/kode_saham/kode_saham.csv",
]

_KODE_RE = re.compile(r"^[A-Z]{4}$")
_KODE_IN = re.compile(r"[A-Z]{4}")


def parse_csv_kode(teks: str) -> list[str]:
    """Ambil kode dari CSV daftar saham (kolom ke-2 = Kode)."""
    kode: list[str] = []
    for baris in teks.splitlines():
        parts = baris.split(",")
        if len(parts) < 2:
            continue
        m = _KODE_IN.search(parts[1].strip().upper())  # tangani "AALI" atau "BEI: AALI"
        if m and _KODE_RE.match(m.group()):
            if m.group() != "KODE":  # lewati baris header
                kode.append(m.group())
    return kode


def _dari_csv(url: str) -> list[str]:
    import requests

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse_csv_kode(resp.text)


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

    Union seluruh sumber CSV; bila semua gagal, pakai file fallback.
    """
    kode: set[str] = set()
    for url in SUMBER_CSV:
        try:
            kode.update(_dari_csv(url))
        except Exception:
            continue
    if not kode:
        kode.update(_dari_file(fallback_file or FALLBACK_FILE))
    return sorted(kode)
