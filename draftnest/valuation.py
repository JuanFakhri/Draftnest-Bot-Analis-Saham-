"""Pilar Valuasi — dua jalur paralel sesuai gambar.

Relative Valuation : PER, PBV dibanding rata-rata sektor.
Absolute Valuation : DCF sederhana (proyeksi FCF + terminal value Gordon).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Emiten


def _bagi(a: float, b: float) -> Optional[float]:
    if b == 0:
        return None
    return a / b


@dataclass
class RelativeValuation:
    eps: Optional[float]
    bvps: Optional[float]
    per: Optional[float]
    pbv: Optional[float]
    per_sektor: Optional[float]
    pbv_sektor: Optional[float]
    # harga wajar tersirat dari rata-rata sektor
    harga_wajar_per: Optional[float]
    harga_wajar_pbv: Optional[float]
    # Fair Value (Mean PER & PBV) — metode rata-rata historis emiten sendiri
    mean_per: Optional[float]
    mean_pbv: Optional[float]
    fair_value_per: Optional[float]      # Mean PER x EPS
    fair_value_pbv: Optional[float]      # Mean PBV x BVPS
    fair_value: Optional[float]          # rata-rata kedua fair value
    mos_fair_value: Optional[float]      # margin of safety thd fair value


@dataclass
class AbsoluteValuation:
    fcf_dasar: float
    growth_rate: float
    discount_rate: float
    terminal_growth: float
    tahun_proyeksi: int
    fcf_proyeksi: list[float]
    pv_fcf: list[float]
    terminal_value: float
    pv_terminal: float
    enterprise_value: float
    nilai_intrinsik_per_saham: Optional[float]


@dataclass
class HasilValuasi:
    harga_saham: float
    relative: RelativeValuation
    absolute: AbsoluteValuation
    # ringkasan margin of safety terhadap DCF
    margin_of_safety: Optional[float]


def _relative(emiten: Emiten) -> RelativeValuation:
    lap = emiten.laporan_terbaru()
    pasar = emiten.pasar
    assert pasar is not None

    eps = _bagi(lap.laba_bersih, pasar.saham_beredar)
    bvps = _bagi(lap.total_ekuitas, pasar.saham_beredar)
    per = _bagi(pasar.harga_saham, eps) if eps else None
    pbv = _bagi(pasar.harga_saham, bvps) if bvps else None

    harga_wajar_per = (pasar.per_sektor * eps) if (pasar.per_sektor and eps) else None
    harga_wajar_pbv = (pasar.pbv_sektor * bvps) if (pasar.pbv_sektor and bvps) else None

    # Fair Value (Mean PER & PBV) — studi kasus MAHA:
    #   Fair Value P/E  = Mean PER (3thn) x EPS
    #   Fair Value PBV  = Mean PBV (3thn) x BVPS
    #   Fair Value      = rata-rata dari fair value yang tersedia
    #   Margin of Safety= (Fair Value - Harga) / Fair Value
    fv_per = (pasar.mean_per_3y * eps) if (pasar.mean_per_3y and eps) else None
    fv_pbv = (pasar.mean_pbv_3y * bvps) if (pasar.mean_pbv_3y and bvps) else None
    tersedia = [x for x in (fv_per, fv_pbv) if x is not None]
    fair_value = sum(tersedia) / len(tersedia) if tersedia else None
    mos_fair = ((fair_value - pasar.harga_saham) / fair_value) if fair_value else None

    return RelativeValuation(
        eps=eps, bvps=bvps, per=per, pbv=pbv,
        per_sektor=pasar.per_sektor, pbv_sektor=pasar.pbv_sektor,
        harga_wajar_per=harga_wajar_per, harga_wajar_pbv=harga_wajar_pbv,
        mean_per=pasar.mean_per_3y, mean_pbv=pasar.mean_pbv_3y,
        fair_value_per=fv_per, fair_value_pbv=fv_pbv,
        fair_value=fair_value, mos_fair_value=mos_fair,
    )


def _absolute(emiten: Emiten) -> AbsoluteValuation:
    lap = emiten.laporan_terbaru()
    pasar = emiten.pasar
    assert pasar is not None

    fcf0 = lap.fcf()
    g = pasar.growth_rate
    r = pasar.discount_rate
    gt = pasar.terminal_growth
    n = pasar.tahun_proyeksi

    fcf_proyeksi: list[float] = []
    pv_fcf: list[float] = []
    fcf = fcf0
    for t in range(1, n + 1):
        fcf = fcf * (1 + g)
        fcf_proyeksi.append(fcf)
        pv_fcf.append(fcf / ((1 + r) ** t))

    # Terminal value (Gordon growth) di akhir tahun-n, lalu diskonto ke sekarang.
    if r > gt:
        terminal_value = fcf_proyeksi[-1] * (1 + gt) / (r - gt)
    else:
        # r <= gt tidak valid untuk Gordon; pakai kelipatan konservatif.
        terminal_value = fcf_proyeksi[-1] * 10
    pv_terminal = terminal_value / ((1 + r) ** n)

    enterprise_value = sum(pv_fcf) + pv_terminal
    nilai_intrinsik = _bagi(enterprise_value, pasar.saham_beredar)

    return AbsoluteValuation(
        fcf_dasar=fcf0, growth_rate=g, discount_rate=r, terminal_growth=gt,
        tahun_proyeksi=n, fcf_proyeksi=fcf_proyeksi, pv_fcf=pv_fcf,
        terminal_value=terminal_value, pv_terminal=pv_terminal,
        enterprise_value=enterprise_value, nilai_intrinsik_per_saham=nilai_intrinsik,
    )


def analisis_valuasi(emiten: Emiten) -> HasilValuasi:
    if emiten.pasar is None:
        raise ValueError("Data pasar (harga & saham beredar) diperlukan untuk valuasi.")

    rel = _relative(emiten)
    abs_ = _absolute(emiten)

    mos = None
    if abs_.nilai_intrinsik_per_saham:
        mos = (abs_.nilai_intrinsik_per_saham - emiten.pasar.harga_saham) / abs_.nilai_intrinsik_per_saham

    return HasilValuasi(
        harga_saham=emiten.pasar.harga_saham,
        relative=rel,
        absolute=abs_,
        margin_of_safety=mos,
    )
