"""Pilar Kuantitatif — "Data Olahannya".

Menghitung rasio kunci secara deterministik dari 3 laporan keuangan.
Hasil di sini yang nanti dikirim ke Claude untuk diinterpretasi & diberi skor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Emiten, LaporanTahunan


def _bagi(a: float, b: float) -> Optional[float]:
    """Pembagian aman: None bila penyebut nol."""
    if b == 0:
        return None
    return a / b


def _cagr(awal: float, akhir: float, periode: int) -> Optional[float]:
    """Compound Annual Growth Rate. None bila tak terdefinisi."""
    if periode <= 0 or awal <= 0 or akhir <= 0:
        return None
    return (akhir / awal) ** (1 / periode) - 1


@dataclass
class RasioKunci:
    tahun: int
    roe: Optional[float]                # Return on Equity
    roa: Optional[float]                # Return on Assets
    der: Optional[float]               # Debt to Equity Ratio
    current_ratio: Optional[float]     # Likuiditas
    net_profit_margin: Optional[float]
    gross_profit_margin: Optional[float]
    operating_margin: Optional[float]


@dataclass
class RingkasanKuantitatif:
    rasio_terbaru: RasioKunci
    rasio_historis: list[RasioKunci]
    growth_pendapatan: Optional[float]   # CAGR
    growth_laba_bersih: Optional[float]  # CAGR
    tahun_data: list[int]


def hitung_rasio(lap: LaporanTahunan) -> RasioKunci:
    return RasioKunci(
        tahun=lap.tahun,
        roe=_bagi(lap.laba_bersih, lap.total_ekuitas),
        roa=_bagi(lap.laba_bersih, lap.total_aset),
        der=_bagi(lap.total_liabilitas, lap.total_ekuitas),
        current_ratio=_bagi(lap.aset_lancar, lap.liabilitas_lancar),
        net_profit_margin=_bagi(lap.laba_bersih, lap.pendapatan),
        gross_profit_margin=_bagi(lap.laba_kotor, lap.pendapatan),
        operating_margin=_bagi(lap.laba_operasi, lap.pendapatan),
    )


def analisis_kuantitatif(emiten: Emiten) -> RingkasanKuantitatif:
    laporan = emiten.laporan_urut()
    rasio = [hitung_rasio(l) for l in laporan]

    growth_pendapatan = None
    growth_laba = None
    if len(laporan) >= 2:
        periode = laporan[-1].tahun - laporan[0].tahun
        growth_pendapatan = _cagr(laporan[0].pendapatan, laporan[-1].pendapatan, periode)
        growth_laba = _cagr(laporan[0].laba_bersih, laporan[-1].laba_bersih, periode)

    return RingkasanKuantitatif(
        rasio_terbaru=rasio[-1],
        rasio_historis=rasio,
        growth_pendapatan=growth_pendapatan,
        growth_laba_bersih=growth_laba,
        tahun_data=[l.tahun for l in laporan],
    )
