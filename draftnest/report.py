"""Penggabung 3 pilar menjadi satu laporan skor + rekomendasi.

Alur (sesuai poin 4 pada spesifikasi):
  1. Muat data emiten
  2. Olah data keuangan -> rasio & valuasi (deterministik)
  3. Kirim ke Claude dgn 3 prompt terpisah (kualitatif, kuantitatif, valuasi)
  4. Gabungkan output jadi satu laporan skor + kesimpulan rekomendasi
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from . import forecast as F
from . import ratios as R
from . import scoring as S
from . import valuation as V
from .analyzers import (
    analisis_kualitatif,
    analisis_kuantitatif_llm,
    analisis_valuasi_llm,
)
from .client import ClaudeClient
from .models import Emiten

# Bobot antar pilar untuk skor akhir.
BOBOT = {"kualitatif": 0.35, "kuantitatif": 0.35, "valuasi": 0.30}


@dataclass
class HasilAnalisis:
    emiten: Emiten
    kuantitatif_data: R.RingkasanKuantitatif
    proyeksi_data: F.HasilProyeksi
    valuasi_data: Optional[V.HasilValuasi]
    ramalan_harga: Optional[F.RamalanHarga]
    kualitatif_llm: Optional[dict[str, Any]]
    kuantitatif_llm: Optional[dict[str, Any]]
    valuasi_llm: Optional[dict[str, Any]]
    skor_pilar: dict[str, Optional[float]]
    skor_akhir: Optional[float]
    rekomendasi: str


def _rata_skor(hasil: Optional[dict[str, Any]], field_poin: list[str]) -> Optional[float]:
    if not hasil:
        return None
    skor = [
        hasil[k]["skor"]
        for k in field_poin
        if k in hasil and hasil[k].get("skor") is not None
    ]
    return sum(skor) / len(skor) if skor else None


def _rekomendasi(skor: Optional[float], status_valuasi: Optional[str]) -> str:
    if skor is None:
        return "TAHAN (data tidak cukup untuk memberi skor)"

    if skor >= 7.5:
        rec = "BELI"
    elif skor >= 5.5:
        rec = "TAHAN"
    else:
        rec = "JUAL"

    # Penyesuaian: overvalued berat menurunkan keyakinan beli.
    if rec == "BELI" and status_valuasi == "overvalued":
        rec = "TAHAN (skor kuat namun valuasi overvalued)"
    return rec


def jalankan_analisis(emiten: Emiten, client: Optional[ClaudeClient]) -> HasilAnalisis:
    # Langkah 2 — olah data deterministik.
    kuant = R.analisis_kuantitatif(emiten)
    proyeksi = F.proyeksi_tahun_depan(emiten)
    valu = V.analisis_valuasi(emiten) if emiten.pasar else None
    ramalan = F.ramalan_harga(emiten, proyeksi, valu)

    # Langkah 2b — skor deterministik dari data (tanpa AI) untuk KETIGA pilar.
    # Ini membuat analisis penuh (skor + rekomendasi) berjalan hanya dari angka.
    kual_det, kuant_det, valu_det = S.analisis_deterministik(emiten, kuant, valu, proyeksi)

    # Langkah 3 — Claude opsional untuk MEMPERKAYA narasi. Skor tetap
    # deterministik sebagai dasar; bila client tersedia, hasil LLM menimpa.
    kual_llm = kual_det
    kuant_llm = kuant_det
    valu_llm = valu_det
    if client is not None:
        kual_llm = analisis_kualitatif(client, emiten)
        kuant_llm = analisis_kuantitatif_llm(client, emiten.profil.kode, kuant)
        if valu is not None:
            valu_llm = analisis_valuasi_llm(client, emiten.profil.kode, valu, proyeksi)

    # Langkah 4 — agregasi skor.
    skor_pilar: dict[str, Optional[float]] = {
        "kualitatif": _rata_skor(
            kual_llm,
            ["model_bisnis", "manajemen", "keunggulan_kompetitif", "prospek_industri"],
        ),
        "kuantitatif": _rata_skor(
            kuant_llm,
            ["profitabilitas", "solvabilitas", "likuiditas", "pertumbuhan"],
        ),
        "valuasi": _rata_skor(valu_llm, ["relative_valuation", "absolute_valuation"]),
    }

    tersedia = {k: v for k, v in skor_pilar.items() if v is not None}
    skor_akhir: Optional[float] = None
    if tersedia:
        total_bobot = sum(BOBOT[k] for k in tersedia)
        skor_akhir = sum(BOBOT[k] * v for k, v in tersedia.items()) / total_bobot

    status_valuasi = valu_llm.get("status") if valu_llm else None
    rekomendasi = _rekomendasi(skor_akhir, status_valuasi)

    return HasilAnalisis(
        emiten=emiten,
        kuantitatif_data=kuant,
        proyeksi_data=proyeksi,
        valuasi_data=valu,
        ramalan_harga=ramalan,
        kualitatif_llm=kual_llm,
        kuantitatif_llm=kuant_llm,
        valuasi_llm=valu_llm,
        skor_pilar=skor_pilar,
        skor_akhir=skor_akhir,
        rekomendasi=rekomendasi,
    )
