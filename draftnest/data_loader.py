"""Memuat data emiten dari file JSON terstruktur.

Ini adalah "port" data. Sumber data untuk Indonesia (IDX, RTI, Stockbit,
laporankeuangan.web.id, dsb.) bisa ditulis ke format JSON yang sama, atau
kembangkan fungsi fetch/scraping tersendiri yang menghasilkan objek `Emiten`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DataPasar, Emiten, LaporanTahunan, ProfilEmiten


def _profil(d: dict[str, Any]) -> ProfilEmiten:
    return ProfilEmiten(
        kode=d["kode"],
        nama=d["nama"],
        sektor=d.get("sektor", ""),
        sub_sektor=d.get("sub_sektor", ""),
        deskripsi_bisnis=d.get("deskripsi_bisnis", ""),
        manajemen=d.get("manajemen", ""),
        keunggulan_kompetitif=d.get("keunggulan_kompetitif", ""),
        prospek_industri=d.get("prospek_industri", ""),
        berita_terkini=d.get("berita_terkini", ""),
    )


def _laporan(d: dict[str, Any]) -> LaporanTahunan:
    return LaporanTahunan(
        tahun=int(d["tahun"]),
        total_aset=float(d["total_aset"]),
        aset_lancar=float(d["aset_lancar"]),
        total_liabilitas=float(d["total_liabilitas"]),
        liabilitas_lancar=float(d["liabilitas_lancar"]),
        total_ekuitas=float(d["total_ekuitas"]),
        pendapatan=float(d["pendapatan"]),
        laba_kotor=float(d["laba_kotor"]),
        laba_operasi=float(d["laba_operasi"]),
        laba_bersih=float(d["laba_bersih"]),
        arus_kas_operasi=float(d["arus_kas_operasi"]),
        arus_kas_investasi=float(d["arus_kas_investasi"]),
        arus_kas_pendanaan=float(d["arus_kas_pendanaan"]),
        free_cash_flow=(
            float(d["free_cash_flow"]) if d.get("free_cash_flow") is not None else None
        ),
    )


def _pasar(d: dict[str, Any]) -> DataPasar:
    return DataPasar(
        harga_saham=float(d["harga_saham"]),
        saham_beredar=float(d["saham_beredar"]),
        per_sektor=d.get("per_sektor"),
        pbv_sektor=d.get("pbv_sektor"),
        mean_per_3y=d.get("mean_per_3y"),
        mean_pbv_3y=d.get("mean_pbv_3y"),
        growth_rate=float(d.get("growth_rate", 0.08)),
        discount_rate=float(d.get("discount_rate", 0.11)),
        terminal_growth=float(d.get("terminal_growth", 0.03)),
        tahun_proyeksi=int(d.get("tahun_proyeksi", 5)),
        dividend_yield=d.get("dividend_yield"),
        dividen_per_saham=d.get("dividen_per_saham"),
        dividen_beruntun=int(d.get("dividen_beruntun", 0) or 0),
    )


def muat_emiten(path: str | Path) -> Emiten:
    """Baca file JSON emiten dan validasi field wajibnya."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if "profil" not in data:
        raise ValueError("File emiten wajib memiliki objek 'profil'.")
    if not data.get("laporan"):
        raise ValueError("File emiten wajib memiliki daftar 'laporan' (min. 1 tahun).")

    return Emiten(
        profil=_profil(data["profil"]),
        laporan=[_laporan(x) for x in data["laporan"]],
        pasar=_pasar(data["pasar"]) if data.get("pasar") else None,
    )
