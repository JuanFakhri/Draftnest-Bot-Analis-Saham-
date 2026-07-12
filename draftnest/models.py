"""Struktur data input per emiten.

Semua angka keuangan memakai satuan yang konsisten (mis. miliar Rupiah).
Yang penting: konsisten antar-field, karena semua rasio berupa pembagian.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LaporanTahunan:
    """Data 3 laporan keuangan untuk satu tahun buku.

    Memetakan langsung ke pilar Kuantitatif pada gambar:
    Neraca (aset/liabilitas/ekuitas), Laba Rugi (pendapatan/laba),
    dan Arus Kas (operasi/investasi/pendanaan).
    """

    tahun: int

    # --- Neraca ---
    total_aset: float
    aset_lancar: float
    total_liabilitas: float
    liabilitas_lancar: float
    total_ekuitas: float

    # --- Laba Rugi ---
    pendapatan: float
    laba_kotor: float
    laba_operasi: float
    laba_bersih: float

    # --- Arus Kas ---
    arus_kas_operasi: float
    arus_kas_investasi: float
    arus_kas_pendanaan: float

    # Opsional: dipakai untuk DCF (Free Cash Flow). Bila None dihitung
    # dari arus kas operasi + arus kas investasi (proxy capex).
    free_cash_flow: Optional[float] = None

    def fcf(self) -> float:
        if self.free_cash_flow is not None:
            return self.free_cash_flow
        # Proxy sederhana: FCF ~= CFO + CFI (CFI biasanya negatif = capex)
        return self.arus_kas_operasi + self.arus_kas_investasi


@dataclass
class ProfilEmiten:
    """Data kualitatif per emiten (pilar Kualitatif)."""

    kode: str
    nama: str
    sektor: str
    sub_sektor: str = ""
    deskripsi_bisnis: str = ""
    manajemen: str = ""
    keunggulan_kompetitif: str = ""
    prospek_industri: str = ""
    berita_terkini: str = ""


@dataclass
class DataPasar:
    """Data pasar & pembanding untuk valuasi (pilar Valuasi)."""

    harga_saham: float           # harga per lembar (Rupiah)
    saham_beredar: float         # jumlah lembar saham (dalam satuan yang sama dgn laporan, mis. miliar lembar)

    # Rata-rata sektor untuk Relative Valuation
    per_sektor: Optional[float] = None
    pbv_sektor: Optional[float] = None

    # Asumsi untuk Absolute Valuation (DCF)
    growth_rate: float = 0.08        # asumsi pertumbuhan FCF tahap-1
    discount_rate: float = 0.11      # WACC / required return
    terminal_growth: float = 0.03    # pertumbuhan terminal (Gordon)
    tahun_proyeksi: int = 5


@dataclass
class Emiten:
    """Gabungan seluruh input untuk satu emiten."""

    profil: ProfilEmiten
    laporan: list[LaporanTahunan] = field(default_factory=list)
    pasar: Optional[DataPasar] = None

    def laporan_terbaru(self) -> LaporanTahunan:
        if not self.laporan:
            raise ValueError("Belum ada laporan keuangan untuk emiten ini.")
        return max(self.laporan, key=lambda x: x.tahun)

    def laporan_urut(self) -> list[LaporanTahunan]:
        return sorted(self.laporan, key=lambda x: x.tahun)
