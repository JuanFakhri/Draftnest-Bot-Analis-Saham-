"""Skoring deterministik (tanpa AI) untuk pilar Kuantitatif & Valuasi.

Bila data keuangan & pasar sudah tersedia, kita bisa memberi skor 1-10 +
justifikasi langsung dari angka — tanpa perlu memanggil Claude. Output-nya
sengaja dibuat menyerupai bentuk keluaran analyzer LLM (lihat
`analyzers/kuantitatif.py` & `analyzers/valuasi.py`) sehingga bisa dipakai
langsung oleh agregator di `report.py`:

  Kuantitatif -> {"profitabilitas": {"skor","justifikasi"}, "solvabilitas": ...,
                  "likuiditas": ..., "pertumbuhan": ..., "ringkasan": str}
  Valuasi     -> {"relative_valuation": {...}, "absolute_valuation": {...},
                  "status": str, "kesimpulan_valuasi": str}

Skor mengikuti ambang (threshold) yang wajar untuk emiten IDX. Semuanya
deterministik: input sama -> output sama.
"""

from __future__ import annotations

from typing import Any, Optional

from . import forecast as F
from . import ratios as R
from . import valuation as V
from .models import Emiten


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x: Optional[float]) -> str:
    return f"{x:.2f}x" if x is not None else "n/a"


def _rp(x: Optional[float]) -> str:
    return f"Rp{x:,.0f}" if x is not None else "n/a"


def _skor_dari_ambang(nilai: Optional[float], ambang: list[tuple[float, int]],
                      bawah: int) -> Optional[int]:
    """Petakan `nilai` ke skor via daftar (batas, skor) urut menurun.

    ambang berupa [(batas1, skor1), (batas2, skor2), ...] dengan batas menurun.
    Skor pertama yang batas-nya <= nilai yang dipakai; bila tak ada -> `bawah`.
    None -> None (data tidak tersedia).
    """
    if nilai is None:
        return None
    for batas, skor in ambang:
        if nilai >= batas:
            return skor
    return bawah


# ----------------------------- Kuantitatif ----------------------------------

def _skor_profitabilitas(r: R.RasioKunci) -> tuple[Optional[int], str]:
    skor = _skor_dari_ambang(
        r.roe,
        [(0.20, 10), (0.15, 8), (0.10, 7), (0.05, 5), (0.0, 3)],
        bawah=1,
    )
    if skor is None:
        return None, "ROE tidak tersedia — profitabilitas tak bisa dinilai."
    just = (
        f"ROE {_pct(r.roe)}, ROA {_pct(r.roa)}, NPM {_pct(r.net_profit_margin)}. "
    )
    if r.roe is not None and r.roe >= 0.15:
        just += "Profitabilitas kuat, imbal hasil ekuitas di atas rata-rata pasar."
    elif r.roe is not None and r.roe >= 0.05:
        just += "Profitabilitas moderat, masih menghasilkan laba yang sehat."
    else:
        just += "Profitabilitas lemah/negatif, perlu perhatian pada kemampuan mencetak laba."
    return skor, just


def _skor_solvabilitas(r: R.RasioKunci) -> tuple[Optional[int], str]:
    skor = _skor_dari_ambang(
        # DER makin kecil makin baik -> pakai -DER lewat pembalikan manual.
        None if r.der is None else -r.der,
        [(-0.3, 10), (-0.5, 9), (-1.0, 7), (-2.0, 5), (-3.0, 3)],
        bawah=1,
    )
    if skor is None:
        return None, "DER tidak tersedia — solvabilitas tak bisa dinilai."
    just = f"DER {_num(r.der)}. "
    if r.der is not None and r.der <= 0.5:
        just += "Struktur modal konservatif, leverage rendah — risiko solvabilitas kecil."
    elif r.der is not None and r.der <= 1.0:
        just += "Leverage moderat, utang masih dalam batas wajar terhadap ekuitas."
    elif r.der is not None and r.der <= 2.0:
        just += "Leverage cukup tinggi, beban utang perlu dipantau."
    else:
        just += "Leverage sangat tinggi — risiko solvabilitas signifikan."
    return skor, just


def _skor_likuiditas(r: R.RasioKunci) -> tuple[Optional[int], str]:
    skor = _skor_dari_ambang(
        r.current_ratio,
        [(2.0, 9), (1.5, 7), (1.0, 5), (0.75, 3)],
        bawah=2,
    )
    if skor is None:
        return None, "Current Ratio tidak tersedia — likuiditas tak bisa dinilai."
    just = f"Current Ratio {_num(r.current_ratio)}. "
    cr = r.current_ratio
    if cr is not None and cr >= 2.0:
        just += "Likuiditas sangat sehat, aset lancar jauh menutupi kewajiban jangka pendek."
    elif cr is not None and cr >= 1.0:
        just += "Likuiditas memadai, kewajiban jangka pendek tertutupi aset lancar."
    else:
        just += "Likuiditas ketat — aset lancar belum menutupi kewajiban jangka pendek."
    return skor, just


def _skor_pertumbuhan(ringkasan: R.RingkasanKuantitatif) -> tuple[Optional[int], str]:
    # Gabungkan pertumbuhan pendapatan & laba (rata-rata bila keduanya ada).
    komponen = [g for g in (ringkasan.growth_pendapatan, ringkasan.growth_laba_bersih)
                if g is not None]
    if not komponen:
        return None, "Butuh >= 2 tahun data untuk menilai pertumbuhan."
    rata = sum(komponen) / len(komponen)
    skor = _skor_dari_ambang(
        rata,
        [(0.20, 10), (0.10, 8), (0.05, 6), (0.0, 4)],
        bawah=2,
    )
    just = (
        f"CAGR pendapatan {_pct(ringkasan.growth_pendapatan)}, "
        f"CAGR laba {_pct(ringkasan.growth_laba_bersih)}. "
    )
    if rata >= 0.10:
        just += "Pertumbuhan kuat dan konsisten di atas inflasi."
    elif rata >= 0.0:
        just += "Pertumbuhan positif namun moderat."
    else:
        just += "Pertumbuhan negatif — kinerja menurun dibanding awal periode."
    return skor, just


def skor_kuantitatif(ringkasan: R.RingkasanKuantitatif) -> dict[str, Any]:
    """Skor kuantitatif deterministik berbentuk seperti keluaran LLM."""
    r = ringkasan.rasio_terbaru
    prof_s, prof_j = _skor_profitabilitas(r)
    solv_s, solv_j = _skor_solvabilitas(r)
    lik_s, lik_j = _skor_likuiditas(r)
    tum_s, tum_j = _skor_pertumbuhan(ringkasan)

    hasil: dict[str, Any] = {}
    if prof_s is not None:
        hasil["profitabilitas"] = {"skor": prof_s, "justifikasi": prof_j}
    if solv_s is not None:
        hasil["solvabilitas"] = {"skor": solv_s, "justifikasi": solv_j}
    if lik_s is not None:
        hasil["likuiditas"] = {"skor": lik_s, "justifikasi": lik_j}
    if tum_s is not None:
        hasil["pertumbuhan"] = {"skor": tum_s, "justifikasi": tum_j}

    skor_ada = [d["skor"] for d in hasil.values()]
    if skor_ada:
        rata = sum(skor_ada) / len(skor_ada)
        hasil["ringkasan"] = (
            f"Skor kuantitatif rata-rata {rata:.1f}/10 berdasarkan rasio tahun "
            f"{r.tahun} (dihitung dari data, tanpa AI). "
            + prof_j
        )
    return hasil


# ------------------------------- Valuasi ------------------------------------

def _skor_relative(v: V.HasilValuasi) -> tuple[Optional[int], str, Optional[str]]:
    """Skor relative valuation + status berbasis Margin of Safety / PER-PBV.

    Prioritas: Fair Value (Mean PER & PBV) -> MoS. Bila tak ada, bandingkan
    PER/PBV emiten terhadap sektor.
    """
    rel = v.relative
    mos = rel.mos_fair_value
    if mos is not None:
        # MoS positif = harga di bawah fair value = undervalued = menarik.
        skor = _skor_dari_ambang(
            mos,
            [(0.30, 10), (0.15, 9), (0.05, 8), (0.0, 6), (-0.15, 4)],
            bawah=2,
        )
        status = "undervalued" if mos >= 0.05 else "overvalued" if mos <= -0.05 else "fairvalued"
        just = (
            f"Fair Value (Mean PER&PBV) {_rp(rel.fair_value)} vs harga {_rp(v.harga_saham)} "
            f"-> Margin of Safety {_pct(mos)}. "
        )
        just += ("Harga di bawah nilai wajar (diskon)." if mos >= 0.05
                 else "Harga di atas nilai wajar (premium)." if mos <= -0.05
                 else "Harga mendekati nilai wajar.")
        return skor, just, status

    # Fallback: PER & PBV vs sektor (rasio < sektor = lebih murah = lebih baik).
    poin: list[int] = []
    detail: list[str] = []
    if rel.per is not None and rel.per_sektor:
        rasio = rel.per / rel.per_sektor
        poin.append(_skor_dari_ambang(-rasio, [(-0.7, 9), (-1.0, 7), (-1.3, 5)], bawah=3))
        detail.append(f"PER {_num(rel.per)} vs sektor {_num(rel.per_sektor)}")
    if rel.pbv is not None and rel.pbv_sektor:
        rasio = rel.pbv / rel.pbv_sektor
        poin.append(_skor_dari_ambang(-rasio, [(-0.7, 9), (-1.0, 7), (-1.3, 5)], bawah=3))
        detail.append(f"PBV {_num(rel.pbv)} vs sektor {_num(rel.pbv_sektor)}")
    if not poin:
        return None, "Data PER/PBV sektor atau Fair Value tak tersedia.", None
    skor = round(sum(poin) / len(poin))
    status = "undervalued" if skor >= 7 else "overvalued" if skor <= 4 else "fairvalued"
    return skor, "; ".join(detail) + ".", status


def _skor_absolute(v: V.HasilValuasi) -> tuple[Optional[int], str]:
    mos = v.margin_of_safety
    if mos is None:
        return None, "Nilai intrinsik DCF tak tersedia — asumsi/FCF tidak lengkap."
    skor = _skor_dari_ambang(
        mos,
        [(0.30, 10), (0.15, 9), (0.05, 7), (0.0, 6), (-0.20, 4)],
        bawah=2,
    )
    ni = v.absolute.nilai_intrinsik_per_saham
    just = (
        f"Nilai intrinsik DCF {_rp(ni)} vs harga {_rp(v.harga_saham)} "
        f"-> Margin of Safety {_pct(mos)}. "
    )
    if mos >= 0.15:
        just += "Diskon signifikan terhadap nilai intrinsik (menarik, namun sensitif asumsi)."
    elif mos >= 0.0:
        just += "Harga sedikit di bawah nilai intrinsik."
    else:
        just += "Harga di atas nilai intrinsik DCF (premium)."
    return skor, just


def skor_valuasi(v: V.HasilValuasi,
                 proyeksi: Optional[F.HasilProyeksi] = None) -> dict[str, Any]:
    """Skor valuasi deterministik berbentuk seperti keluaran LLM."""
    rel_s, rel_j, rel_status = _skor_relative(v)
    abs_s, abs_j = _skor_absolute(v)

    hasil: dict[str, Any] = {}
    if rel_s is not None:
        hasil["relative_valuation"] = {"skor": rel_s, "justifikasi": rel_j}
    if abs_s is not None:
        hasil["absolute_valuation"] = {"skor": abs_s, "justifikasi": abs_j}

    # Status keseluruhan: utamakan MoS DCF, lalu status relative.
    status = None
    mos = v.margin_of_safety
    if mos is not None:
        status = "undervalued" if mos >= 0.05 else "overvalued" if mos <= -0.05 else "fairvalued"
    elif rel_status is not None:
        status = rel_status
    if status is not None:
        hasil["status"] = status

    if hasil:
        skor_ada = [d["skor"] for d in hasil.values() if isinstance(d, dict) and "skor" in d]
        rata = sum(skor_ada) / len(skor_ada) if skor_ada else None
        label = {"undervalued": "cenderung undervalued",
                 "overvalued": "cenderung overvalued",
                 "fairvalued": "mendekati wajar"}.get(status or "", "belum simpul")
        hasil["kesimpulan_valuasi"] = (
            f"Berdasar hitung data (tanpa AI), harga {label}"
            + (f" dengan skor valuasi rata-rata {rata:.1f}/10. " if rata is not None else ". ")
            + rel_j
        )
        if proyeksi and proyeksi.proyeksi:
            hasil["outlook_tahun_depan"] = (
                f"Proyeksi ekstrapolasi CAGR: pendapatan {_pct(proyeksi.cagr_pendapatan)}, "
                f"laba {_pct(proyeksi.cagr_laba)} per tahun. Angka proyeksi sangat "
                f"sensitif terhadap asumsi pertumbuhan."
            )
    return hasil


# --------------------------- API tingkat-atas -------------------------------

def analisis_deterministik(
    emiten: Emiten,
    kuant: R.RingkasanKuantitatif,
    valu: Optional[V.HasilValuasi],
    proyeksi: Optional[F.HasilProyeksi] = None,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """Kembalikan (skor_kuantitatif, skor_valuasi) deterministik.

    skor_valuasi None bila data pasar/valuasi tak tersedia.
    """
    kuant_skor = skor_kuantitatif(kuant)
    valu_skor = skor_valuasi(valu, proyeksi) if valu is not None else None
    return kuant_skor, valu_skor
