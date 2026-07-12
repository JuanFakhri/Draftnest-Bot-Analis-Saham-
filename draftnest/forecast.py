"""Proyeksi sederhana tahun mendatang berbasis tren CAGR.

Deterministik: memproyeksikan pendapatan & laba bersih memakai CAGR historis,
lalu menurunkan margin. Dipakai untuk memberi konteks 'tahun mendatang' pada
laporan dan prompt AI. Bukan ramalan pasti — hanya ekstrapolasi tren.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Emiten


@dataclass
class TahunProyeksi:
    tahun: int
    pendapatan: float
    laba_bersih: float
    net_margin: Optional[float]


@dataclass
class HasilProyeksi:
    cagr_pendapatan: Optional[float]
    cagr_laba: Optional[float]
    proyeksi: list[TahunProyeksi]


def _cagr(awal: float, akhir: float, periode: int) -> Optional[float]:
    if periode <= 0 or awal <= 0 or akhir <= 0:
        return None
    return (akhir / awal) ** (1 / periode) - 1


def proyeksi_tahun_depan(emiten: Emiten, n_tahun: int = 3) -> HasilProyeksi:
    """Proyeksikan `n_tahun` ke depan dari laporan historis (butuh >= 2 tahun)."""
    lap = emiten.laporan_urut()
    if len(lap) < 2:
        return HasilProyeksi(cagr_pendapatan=None, cagr_laba=None, proyeksi=[])

    periode = lap[-1].tahun - lap[0].tahun
    g_pend = _cagr(lap[0].pendapatan, lap[-1].pendapatan, periode)
    g_laba = _cagr(lap[0].laba_bersih, lap[-1].laba_bersih, periode)

    terakhir = lap[-1]
    pend = terakhir.pendapatan
    laba = terakhir.laba_bersih
    proyeksi: list[TahunProyeksi] = []
    for i in range(1, n_tahun + 1):
        if g_pend is not None:
            pend = pend * (1 + g_pend)
        if g_laba is not None:
            laba = laba * (1 + g_laba)
        margin = (laba / pend) if pend else None
        proyeksi.append(
            TahunProyeksi(
                tahun=terakhir.tahun + i,
                pendapatan=pend,
                laba_bersih=laba,
                net_margin=margin,
            )
        )

    return HasilProyeksi(cagr_pendapatan=g_pend, cagr_laba=g_laba, proyeksi=proyeksi)
