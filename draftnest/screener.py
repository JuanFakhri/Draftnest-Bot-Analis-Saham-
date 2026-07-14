"""Screener saham: saring emiten berdasar kriteria fundamental.

Fokus kriteria pengguna:
  1. Pertumbuhan NAIK tiap tahun (pendapatan & laba konsisten meningkat).
  2. Rutin membagi dividen, dengan yield pada rentang tertentu (mis. 7-15%).
  3. Prospek jangka panjang (20 th) bagus — diproksikan dari kualitas fundamental:
     ROE tinggi & konsisten, leverage terkendali, pertumbuhan positif, moat.

`ringkas_emiten` menghasilkan ringkasan metrik per emiten (dipakai membangun
docs/data/screener.json di pipeline). `lolos` menyaring ringkasan itu memakai
`KriteriaScreener`. Semua deterministik, tanpa AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from . import ratios as R
from . import scoring as S
from .models import Emiten


def naik_tiap_tahun(seri: list[float], min_titik: int = 3) -> Optional[bool]:
    """True bila `seri` naik di SETIAP tahun (menurut urutan diberikan).

    None bila titik data kurang dari `min_titik` (tak cukup untuk menyimpulkan
    konsistensi). Mengabaikan nilai non-positif di depan (mis. tahun phantom).
    """
    bersih = [v for v in seri if v is not None]
    # Buang nol/negatif di depan (phantom / pra-IPO) agar tak salah kesimpulan.
    while bersih and bersih[0] <= 0:
        bersih = bersih[1:]
    if len(bersih) < min_titik:
        return None
    return all(b > a for a, b in zip(bersih, bersih[1:]))


@dataclass
class KriteriaScreener:
    # Pertumbuhan
    wajib_pendapatan_naik: bool = True
    wajib_laba_naik: bool = True
    # Dividen (yield sebagai fraksi: 0.07 = 7%)
    div_yield_min: Optional[float] = 0.07
    div_yield_maks: Optional[float] = 0.15
    div_beruntun_min: int = 3            # minimal tahun berturut membagi dividen
    # Prospek jangka panjang
    prospek_bagus: bool = True
    skor_min: Optional[float] = None     # ambang skor akhir (opsional)


def ringkas_emiten(emiten: Emiten) -> dict[str, Any]:
    """Metrik ringkas satu emiten untuk screener (deterministik)."""
    from .report import jalankan_analisis  # lazy: hindari import berat saat modul dimuat

    lap = emiten.laporan_urut()
    kuant = R.analisis_kuantitatif(emiten)
    r = kuant.rasio_terbaru

    naik_pend = naik_tiap_tahun([l.pendapatan for l in lap])
    naik_laba = naik_tiap_tahun([l.laba_bersih for l in lap])

    # Skor deterministik 3 pilar + rekomendasi (tanpa AI).
    hasil = jalankan_analisis(emiten, None)
    sp = hasil.skor_pilar

    m = emiten.pasar
    div_yield = m.dividend_yield if m else None
    div_beruntun = m.dividen_beruntun if m else 0

    prospek = _prospek_bagus(r, kuant, sp.get("kualitatif"))

    h = emiten.harian
    bsjp = {
        "bsjp_peluang": h.peluang_naik_target if h else None,
        "bsjp_win_rate": h.win_rate if h else None,
        "bsjp_rata_gap": h.rata_gap if h else None,
        "bsjp_volume": h.volume_rata if h else None,
        "bsjp_sampel": h.sampel_hari if h else None,
        "bsjp_target": h.target if h else None,
    } if h else {"bsjp_peluang": None}

    bt = emiten.backtest or {}
    sinyal = {
        "strat1_sinyal": bool(bt.get("s1", {}).get("sinyal_terakhir")),
        "strat2_sinyal": bool(bt.get("s2", {}).get("sinyal_terakhir")),
        "strat_and_sinyal": bool(bt.get("s_and", {}).get("sinyal_terakhir")),
        "strat_or_sinyal": bool(bt.get("s_or", {}).get("sinyal_terakhir")),
    }
    # Hitungan backtest per-saham (agar win rate bisa dihitung ulang untuk subset
    # yang difilter di browser, mis. S2 + skor fundamental / likuiditas).
    for key in ("s1", "s2", "s_or"):
        b = bt.get(key) or {}
        sinyal[f"bt_{key}_sinyal"] = b.get("sinyal", 0)
        sinyal[f"bt_{key}_menang"] = b.get("menang", 0)
        sinyal[f"bt_{key}_hit3"] = b.get("hit3", 0)
        sinyal[f"bt_{key}_ret"] = round(b.get("ret_total", 0.0), 6)

    return {**bsjp, **sinyal,
        "kode": emiten.profil.kode,
        "nama": emiten.profil.nama,
        "sektor": emiten.profil.sektor,
        "harga": m.harga_saham if m else None,
        "tahun": [l.tahun for l in lap],
        "naik_pendapatan": naik_pend,
        "naik_laba": naik_laba,
        "cagr_pendapatan": kuant.growth_pendapatan,
        "cagr_laba": kuant.growth_laba_bersih,
        "roe": r.roe,
        "der": r.der,
        "current_ratio": r.current_ratio,
        "dividend_yield": div_yield,
        "dividen_beruntun": div_beruntun,
        "skor_kualitatif": sp.get("kualitatif"),
        "skor_kuantitatif": sp.get("kuantitatif"),
        "skor_valuasi": sp.get("valuasi"),
        "skor_akhir": hasil.skor_akhir,
        "rekomendasi": hasil.rekomendasi,
        "prospek_bagus": prospek,
    }


def _prospek_bagus(r: R.RasioKunci, kuant: R.RingkasanKuantitatif,
                   skor_kualitatif: Optional[float]) -> bool:
    """Proksi 'prospek 20 tahun bagus': kualitas fundamental yang tahan lama.

    Kombinasi ROE tinggi, leverage terkendali, pertumbuhan positif, dan skor
    kualitatif (moat/manajemen) yang baik.
    """
    roe_ok = r.roe is not None and r.roe >= 0.12
    der_ok = r.der is None or r.der <= 1.5
    tumbuh_ok = (kuant.growth_laba_bersih or 0) >= 0.05 or (kuant.growth_pendapatan or 0) >= 0.05
    kual_ok = skor_kualitatif is not None and skor_kualitatif >= 6.5
    return roe_ok and der_ok and tumbuh_ok and kual_ok


def lolos(r: dict[str, Any], k: KriteriaScreener) -> bool:
    """True bila ringkasan `r` memenuhi seluruh kriteria `k`."""
    if k.wajib_pendapatan_naik and not r.get("naik_pendapatan"):
        return False
    if k.wajib_laba_naik and not r.get("naik_laba"):
        return False

    dy = r.get("dividend_yield")
    if k.div_yield_min is not None:
        if dy is None or dy < k.div_yield_min:
            return False
    if k.div_yield_maks is not None and dy is not None and dy > k.div_yield_maks:
        return False
    if k.div_beruntun_min and (r.get("dividen_beruntun") or 0) < k.div_beruntun_min:
        return False

    if k.prospek_bagus and not r.get("prospek_bagus"):
        return False
    if k.skor_min is not None:
        sa = r.get("skor_akhir")
        if sa is None or sa < k.skor_min:
            return False
    return True


def saring(ringkasan: list[dict[str, Any]], k: Optional[KriteriaScreener] = None) -> list[dict[str, Any]]:
    """Saring & urutkan daftar ringkasan; terbaik (skor akhir) di atas."""
    k = k or KriteriaScreener()
    hasil = [r for r in ringkasan if lolos(r, k)]
    hasil.sort(key=lambda r: (r.get("skor_akhir") or 0), reverse=True)
    return hasil
