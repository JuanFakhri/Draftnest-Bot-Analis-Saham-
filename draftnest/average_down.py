"""Kalkulator Average Down (referensi: file Excel 'Average Down').

Menghitung harga rata-rata, untung/rugi, risiko, dan simulasi berapa lot yang
perlu dibeli untuk menurunkan harga rata-rata ke target. 1 lot = 100 lembar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SAHAM_PER_LOT = 100


@dataclass
class Pembelian:
    lot: float
    harga: float  # harga beli per lembar (Rupiah)

    def saham(self) -> float:
        return self.lot * SAHAM_PER_LOT

    def modal(self) -> float:
        return self.saham() * self.harga


@dataclass
class HasilAverageDown:
    total_lot: float
    total_saham: float
    total_modal: float
    harga_rata: Optional[float]      # harga rata-rata per lembar
    harga_sekarang: float
    nilai_sekarang: float
    untung_rugi: float
    untung_rugi_pct: Optional[float]
    di_bawah_rata: bool              # harga sekarang < rata-rata (masih nyangkut)
    kenaikan_ke_bep_pct: Optional[float]  # % kenaikan harga utk balik modal
    # Konteks portofolio (opsional, butuh cash)
    persen_investasi: Optional[float]
    risiko: Optional[str]


def hitung(
    pembelian: list[Pembelian], harga_sekarang: float, cash: Optional[float] = None
) -> HasilAverageDown:
    total_lot = sum(p.lot for p in pembelian)
    total_saham = total_lot * SAHAM_PER_LOT
    total_modal = sum(p.modal() for p in pembelian)
    harga_rata = (total_modal / total_saham) if total_saham else None
    nilai_sekarang = total_saham * harga_sekarang
    untung_rugi = nilai_sekarang - total_modal
    untung_rugi_pct = (untung_rugi / total_modal) if total_modal else None
    di_bawah_rata = harga_rata is not None and harga_sekarang < harga_rata
    kenaikan_ke_bep = (
        (harga_rata - harga_sekarang) / harga_sekarang
        if (harga_rata is not None and harga_sekarang)
        else None
    )

    persen_investasi = None
    risiko = None
    if cash and cash > 0:
        persen_investasi = total_modal / cash
        if persen_investasi >= 0.7:
            risiko = "HIGH RISK"
        elif persen_investasi >= 0.4:
            risiko = "MEDIUM RISK"
        else:
            risiko = "LOW RISK"

    return HasilAverageDown(
        total_lot=total_lot,
        total_saham=total_saham,
        total_modal=total_modal,
        harga_rata=harga_rata,
        harga_sekarang=harga_sekarang,
        nilai_sekarang=nilai_sekarang,
        untung_rugi=untung_rugi,
        untung_rugi_pct=untung_rugi_pct,
        di_bawah_rata=di_bawah_rata,
        kenaikan_ke_bep_pct=kenaikan_ke_bep,
        persen_investasi=persen_investasi,
        risiko=risiko,
    )


def lot_untuk_target(
    total_lot_awal: float, harga_rata_awal: float, harga_beli: float, target_rata: float
) -> Optional[float]:
    """Berapa lot dibeli @harga_beli agar rata-rata turun ke target_rata.

    Valid untuk average down: harga_beli < target_rata < harga_rata_awal.
    Kembalikan None bila tak masuk akal (target tak tercapai dengan menambah beli).
    """
    if not (harga_beli < target_rata < harga_rata_awal):
        return None
    s0 = total_lot_awal * SAHAM_PER_LOT
    c0 = s0 * harga_rata_awal
    penyebut = harga_beli - target_rata
    if penyebut == 0:
        return None
    q_saham = (target_rata * s0 - c0) / penyebut
    lot = q_saham / SAHAM_PER_LOT
    return lot if lot > 0 else None
