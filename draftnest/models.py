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

    # Rata-rata historis emiten sendiri (mis. 3 tahun) untuk metode
    # Fair Value (Mean PER & PBV) — lihat studi kasus MAHA.
    mean_per_3y: Optional[float] = None
    mean_pbv_3y: Optional[float] = None

    # Asumsi untuk Absolute Valuation (DCF)
    growth_rate: float = 0.08        # asumsi pertumbuhan FCF tahap-1
    discount_rate: float = 0.11      # WACC / required return
    terminal_growth: float = 0.03    # pertumbuhan terminal (Gordon)
    tahun_proyeksi: int = 5

    # Dividen (opsional) — dipakai screener saham high-dividend.
    dividend_yield: Optional[float] = None     # yield tahunan sbg fraksi (0.08 = 8%)
    dividen_per_saham: Optional[float] = None  # dividen per lembar (12 bln terakhir)
    dividen_beruntun: int = 0                  # jumlah tahun berturut membagi dividen


@dataclass
class StatistikHarian:
    """Statistik overnight gap (close -> open berikutnya) untuk strategi BSJP.

    Semua nilai berupa fraksi (0.03 = 3%). Dihitung dari riwayat harga harian.
    """
    sampel_hari: int                       # jumlah pasangan hari yang dihitung
    peluang_naik_target: Optional[float]   # fraksi hari gap >= target (default 3%)
    win_rate: Optional[float]              # fraksi hari gap > 0
    rata_gap: Optional[float]              # rata-rata overnight return
    median_gap: Optional[float]
    rata_gap_positif: Optional[float]      # rata-rata gap saat positif
    volatilitas_gap: Optional[float]       # stdev overnight return
    volume_rata: Optional[float]           # rata-rata volume harian (likuiditas)
    target: float = 0.03                   # target gap yang dipakai (fraksi)


@dataclass
class Emiten:
    """Gabungan seluruh input untuk satu emiten."""

    profil: ProfilEmiten
    laporan: list[LaporanTahunan] = field(default_factory=list)
    pasar: Optional[DataPasar] = None
    harian: Optional[StatistikHarian] = None
    backtest: Optional[dict] = None   # hitungan backtest strategi (lihat backtest.py)

    def laporan_terbaru(self) -> LaporanTahunan:
        if not self.laporan:
            raise ValueError("Belum ada laporan keuangan untuk emiten ini.")
        return max(self.laporan, key=lambda x: x.tahun)

    def laporan_urut(self) -> list[LaporanTahunan]:
        return sorted(self.laporan, key=lambda x: x.tahun)
