"""Proyeksi sederhana tahun mendatang berbasis tren CAGR.

Deterministik: memproyeksikan pendapatan & laba bersih memakai CAGR historis,
lalu menurunkan margin. Dipakai untuk memberi konteks 'tahun mendatang' pada
laporan dan prompt AI. Bukan ramalan pasti — hanya ekstrapolasi tren.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .models import Emiten
from .ratios import cagr_seri

if TYPE_CHECKING:  # hanya untuk anotasi; hindari impor saat runtime
    from .valuation import HasilValuasi


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


@dataclass
class TargetHarga:
    tahun: int
    eps: Optional[float]
    target_harga: Optional[float]
    potensi_pct: Optional[float]      # (target - harga sekarang) / harga sekarang


@dataclass
class RamalanHarga:
    harga_sekarang: float
    harga_wajar: Optional[float]      # estimasi nilai wajar SAAT INI
    metode_wajar: str                 # sumber nilai wajar (Fair Value / DCF / sektor)
    potensi_wajar_pct: Optional[float]
    multiple_pe: Optional[float]      # kelipatan P/E untuk proyeksi harga ke depan
    metode_multiple: str
    target: list[TargetHarga]
    cagr_harga: Optional[float]       # CAGR harga dari sekarang ke target tahun akhir


def proyeksi_tahun_depan(emiten: Emiten, n_tahun: int = 3) -> HasilProyeksi:
    """Proyeksikan `n_tahun` ke depan dari laporan historis (butuh >= 2 tahun)."""
    lap = emiten.laporan_urut()
    if len(lap) < 2:
        return HasilProyeksi(cagr_pendapatan=None, cagr_laba=None, proyeksi=[])

    g_pend = cagr_seri(lap, lambda l: l.pendapatan)
    g_laba = cagr_seri(lap, lambda l: l.laba_bersih)

    # Tanpa sinyal pertumbuhan sama sekali, proyeksi hanya akan datar & menyesatkan.
    if g_pend is None and g_laba is None:
        return HasilProyeksi(cagr_pendapatan=None, cagr_laba=None, proyeksi=[])

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


def ramalan_harga(
    emiten: Emiten,
    proyeksi: HasilProyeksi,
    valu: Optional["HasilValuasi"] = None,
) -> Optional[RamalanHarga]:
    """Ramalan/target harga saham ke depan (deterministik, tanpa AI).

    Dua bagian:
      1. Nilai wajar SAAT INI — diambil (berurutan) dari Fair Value (Mean PER&PBV),
         lalu nilai intrinsik DCF, lalu harga wajar berbasis sektor.
      2. Target harga TAHUN MENDATANG — EPS proyeksi tiap tahun dikalikan kelipatan
         P/E wajar (Mean PER, atau PER sektor, atau PER berjalan).

    Semua ekstrapolasi, bukan kepastian — sangat sensitif pada asumsi.
    """
    pasar = emiten.pasar
    if pasar is None or not pasar.harga_saham or not pasar.saham_beredar:
        return None

    harga = pasar.harga_saham

    # --- 1. Nilai wajar saat ini (pakai kandidat POSITIF pertama) ---
    harga_wajar: Optional[float] = None
    metode_wajar = "n/a"
    if valu is not None:
        rel = valu.relative
        wajar_sektor = [x for x in (rel.harga_wajar_per, rel.harga_wajar_pbv) if x is not None]
        sektor_avg = sum(wajar_sektor) / len(wajar_sektor) if wajar_sektor else None
        kandidat = [
            (rel.fair_value, rel.metode_fair_value or "Fair Value"),
            (valu.absolute.nilai_intrinsik_per_saham, "Nilai intrinsik DCF"),
            (sektor_avg, "Harga wajar rata-rata sektor (PER/PBV)"),
        ]
        for nilai, metode in kandidat:
            if nilai is not None and nilai > 0:
                harga_wajar, metode_wajar = nilai, metode
                break
    potensi_wajar = ((harga_wajar - harga) / harga) if harga_wajar else None

    # --- 2. Kelipatan P/E untuk proyeksi ke depan ---
    multiple = None
    metode_multiple = "n/a"
    eps_now = (emiten.laporan_terbaru().laba_bersih / pasar.saham_beredar) if pasar.saham_beredar else None
    if pasar.mean_per_3y:
        multiple, metode_multiple = pasar.mean_per_3y, "Mean PER 3 tahun"
    elif pasar.per_sektor:
        multiple, metode_multiple = pasar.per_sektor, "PER sektor"
    elif eps_now and eps_now > 0:
        multiple, metode_multiple = harga / eps_now, "PER berjalan (harga/EPS)"

    target: list[TargetHarga] = []
    for p in proyeksi.proyeksi:
        eps = (p.laba_bersih / pasar.saham_beredar) if pasar.saham_beredar else None
        th = (multiple * eps) if (multiple is not None and eps is not None) else None
        # Harga tak boleh negatif; EPS/multiple negatif -> target tak bermakna.
        if th is not None and th <= 0:
            th = None
        pot = ((th - harga) / harga) if th else None
        target.append(TargetHarga(tahun=p.tahun, eps=eps, target_harga=th, potensi_pct=pot))

    cagr_harga = None
    if target and target[-1].target_harga and target[-1].target_harga > 0 and harga > 0:
        n = len(target)
        cagr_harga = (target[-1].target_harga / harga) ** (1 / n) - 1

    return RamalanHarga(
        harga_sekarang=harga,
        harga_wajar=harga_wajar,
        metode_wajar=metode_wajar,
        potensi_wajar_pct=potensi_wajar,
        multiple_pe=multiple,
        metode_multiple=metode_multiple,
        target=target,
        cagr_harga=cagr_harga,
    )
