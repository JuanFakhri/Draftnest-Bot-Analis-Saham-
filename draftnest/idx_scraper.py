"""Modul pengambilan data otomatis dari IDX (Bursa Efek Indonesia).

Dua jalur:
1. Endpoint JSON IDX untuk profil emiten + harga/saham beredar (best-effort;
   IDX memakai proteksi bot sehingga bisa terblokir/rate-limit).
2. Parser dokumen XBRL (instance) laporan keuangan IDX — jalur paling andal,
   karena file XBRL bisa diunduh manual dari idx.co.id lalu diparse offline.

Semua angka dari XBRL memakai satuan penuh (Rupiah / lembar penuh) dan konsisten
satu sama lain, sehingga rasio & valuasi tetap benar.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional, Union

from .models import DataPasar, Emiten, LaporanTahunan, ProfilEmiten

IDX_BASE = "https://www.idx.co.id/primary"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class IDXError(RuntimeError):
    """Kesalahan saat mengambil data dari IDX."""


# --------------------------------------------------------------------------- #
# Bagian 1 — Endpoint JSON IDX (profil + harga). Best-effort.
# --------------------------------------------------------------------------- #

def _get_json(url: str, timeout: int = 20) -> Any:
    import requests  # impor lazy agar mode offline tak butuh requests

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.idx.co.id/",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:  # pragma: no cover - jaringan
        raise IDXError(f"Gagal menghubungi IDX: {e}") from e

    if resp.status_code != 200:
        raise IDXError(
            f"IDX membalas HTTP {resp.status_code}. Endpoint kemungkinan diblokir "
            f"proteksi bot; unduh XBRL manual lalu pakai parser (--xbrl)."
        )
    try:
        return resp.json()
    except ValueError as e:
        raise IDXError("Respons IDX bukan JSON (kemungkinan halaman proteksi bot).") from e


def ambil_profil(kode: str) -> dict[str, Any]:
    """Ambil profil perusahaan (nama, sektor, jumlah saham) dari IDX."""
    kode = kode.upper()
    url = (
        f"{IDX_BASE}/ListedCompany/GetCompanyProfilesDetail"
        f"?KodeEmiten={kode}&language=id-id"
    )
    data = _get_json(url)
    # Struktur IDX bisa berubah; ambil defensif.
    inti = data.get("Profiles", [{}])
    row = inti[0] if isinstance(inti, list) and inti else data
    return row if isinstance(row, dict) else {}


def ambil_ringkasan_saham(kode: str) -> dict[str, Any]:
    """Ambil harga & jumlah saham tercatat (best-effort)."""
    kode = kode.upper()
    url = (
        f"{IDX_BASE}/TradingSummary/GetStockSummary"
        f"?length=1&start=0&code={kode}"
    )
    data = _get_json(url)
    rows = data.get("data") or data.get("Data") or []
    return rows[0] if isinstance(rows, list) and rows else {}


def _num(d: dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            try:
                return float(str(d[k]).replace(",", ""))
            except (TypeError, ValueError):
                continue
    return None


def _str(d: dict[str, Any], *keys: str) -> str:
    for k in keys:
        if d.get(k):
            return str(d[k])
    return ""


def bangun_profil_pasar(kode: str) -> tuple[ProfilEmiten, Optional[DataPasar]]:
    """Rakit ProfilEmiten + DataPasar dari endpoint IDX (best-effort).

    Bila endkoint terblokir, lempar IDXError agar caller bisa fallback.
    """
    kode = kode.upper()
    prof = ambil_profil(kode)
    profil = ProfilEmiten(
        kode=kode,
        nama=_str(prof, "NamaEmiten", "Nama", "CompanyName") or kode,
        sektor=_str(prof, "Sektor", "Sector", "IndustrySector"),
        sub_sektor=_str(prof, "SubSektor", "SubSector", "IndustrySubSector"),
        deskripsi_bisnis=_str(prof, "KegiatanUsaha", "BusinessActivity"),
    )

    pasar: Optional[DataPasar] = None
    try:
        rk = ambil_ringkasan_saham(kode)
        harga = _num(rk, "Close", "Previous", "Penutupan")
        saham = _num(prof, "JumlahSaham", "ListedShares", "Saham") or _num(
            rk, "ListedShares"
        )
        if harga and saham:
            pasar = DataPasar(harga_saham=harga, saham_beredar=saham)
    except IDXError:
        pasar = None  # harga opsional; jangan gagalkan seluruh proses

    return profil, pasar


# --------------------------------------------------------------------------- #
# Bagian 2 — Parser XBRL (instance) laporan keuangan IDX. Andal & offline.
# --------------------------------------------------------------------------- #

# Peta konsep XBRL (localname) IDX/IFRS -> field LaporanTahunan.
# Tiap field mencoba beberapa kandidat nama konsep (yang pertama ketemu dipakai).
_XBRL_MAP: dict[str, list[str]] = {
    "total_aset": ["Assets"],
    "aset_lancar": ["CurrentAssets"],
    "total_liabilitas": ["Liabilities"],
    "liabilitas_lancar": ["CurrentLiabilities"],
    "total_ekuitas": ["EquityAttributableToOwnersOfParent", "Equity"],
    "pendapatan": ["SalesAndRevenue", "Revenue", "RevenueFromContractsWithCustomers"],
    "laba_kotor": ["GrossProfit"],
    "laba_operasi": ["ProfitLossFromOperatingActivities", "ProfitFromOperation"],
    "laba_bersih": ["ProfitLoss", "ProfitLossForThePeriod"],
    "arus_kas_operasi": [
        "NetCashFlowsReceivedFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ],
    "arus_kas_investasi": [
        "NetCashFlowsReceivedFromUsedInInvestingActivities",
        "CashFlowsFromUsedInInvestingActivities",
    ],
    "arus_kas_pendanaan": [
        "NetCashFlowsReceivedFromUsedInFinancingActivities",
        "CashFlowsFromUsedInFinancingActivities",
    ],
}

# Konteks IDX untuk periode berjalan biasanya mengandung "CurrentYear".
_KONTEKS_BERJALAN = "CurrentYear"


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_xbrl(source: Union[str, Path, bytes], tahun: Optional[int] = None) -> LaporanTahunan:
    """Parse satu dokumen XBRL instance IDX menjadi LaporanTahunan.

    source: path file, atau bytes isi XBRL.
    tahun : override tahun buku; bila None dicoba dibaca dari konteks/tanggal.
    """
    if isinstance(source, (str, Path)):
        root = ET.parse(str(source)).getroot()
    else:
        root = ET.fromstring(source)

    # Kumpulkan nilai per konsep, utamakan konteks periode berjalan.
    nilai: dict[str, float] = {}
    tanggal_akhir: Optional[str] = None

    for el in root.iter():
        ln = _localname(el.tag)
        ctx = el.attrib.get("contextRef", "")
        teks = (el.text or "").strip()

        if ln in ("CurrentPeriodEndDate", "DocumentPeriodEndDate") and teks:
            tanggal_akhir = teks

        if not teks:
            continue
        for field, kandidat in _XBRL_MAP.items():
            if ln in kandidat:
                try:
                    val = float(teks.replace(",", ""))
                except ValueError:
                    continue
                # Prioritaskan konteks berjalan; kalau field belum terisi, isi.
                if field not in nilai or _KONTEKS_BERJALAN in ctx:
                    nilai[field] = val

    if not nilai:
        raise IDXError(
            "Tidak menemukan konsep keuangan pada XBRL. Pastikan file adalah "
            "'instance.xbrl' laporan keuangan IDX, bukan file taksonomi."
        )

    if tahun is None:
        if tanggal_akhir and len(tanggal_akhir) >= 4 and tanggal_akhir[:4].isdigit():
            tahun = int(tanggal_akhir[:4])
        else:
            raise IDXError("Tahun buku tidak terdeteksi dari XBRL; berikan lewat --year.")

    wajib = ["total_aset", "total_ekuitas", "pendapatan", "laba_bersih"]
    hilang = [w for w in wajib if w not in nilai]
    if hilang:
        raise IDXError(
            f"Konsep wajib tidak lengkap di XBRL: {', '.join(hilang)}. "
            f"Lengkapi manual pada JSON hasil."
        )

    return LaporanTahunan(
        tahun=tahun,
        total_aset=nilai.get("total_aset", 0.0),
        aset_lancar=nilai.get("aset_lancar", 0.0),
        total_liabilitas=nilai.get("total_liabilitas", 0.0),
        liabilitas_lancar=nilai.get("liabilitas_lancar", 0.0),
        total_ekuitas=nilai.get("total_ekuitas", 0.0),
        pendapatan=nilai.get("pendapatan", 0.0),
        laba_kotor=nilai.get("laba_kotor", 0.0),
        laba_operasi=nilai.get("laba_operasi", 0.0),
        laba_bersih=nilai.get("laba_bersih", 0.0),
        arus_kas_operasi=nilai.get("arus_kas_operasi", 0.0),
        arus_kas_investasi=nilai.get("arus_kas_investasi", 0.0),
        arus_kas_pendanaan=nilai.get("arus_kas_pendanaan", 0.0),
    )


# --------------------------------------------------------------------------- #
# Perakit tingkat tinggi
# --------------------------------------------------------------------------- #

def bangun_emiten(
    kode: str,
    xbrl_files: Optional[list[Union[str, Path]]] = None,
    tahun: Optional[int] = None,
    ambil_pasar: bool = True,
) -> Emiten:
    """Rakit objek Emiten dari IDX (profil/harga) + XBRL (laporan keuangan).

    Minimal salah satu sumber harus berhasil. Bagian yang gagal diambil
    dibiarkan kosong untuk dilengkapi manual.
    """
    kode = kode.upper()

    profil = ProfilEmiten(kode=kode, nama=kode, sektor="")
    pasar: Optional[DataPasar] = None
    if ambil_pasar:
        try:
            profil, pasar = bangun_profil_pasar(kode)
        except IDXError:
            pass  # lanjut dengan profil minimal

    laporan: list[LaporanTahunan] = []
    for f in xbrl_files or []:
        laporan.append(parse_xbrl(f, tahun=tahun))

    if not laporan and pasar is None:
        raise IDXError(
            "Tidak ada data yang berhasil diambil (endpoint IDX terblokir & "
            "tidak ada XBRL). Unduh XBRL dari idx.co.id lalu pakai --xbrl."
        )

    return Emiten(profil=profil, laporan=laporan, pasar=pasar)


def emiten_ke_dict(emiten: Emiten) -> dict[str, Any]:
    """Serialisasi Emiten -> dict JSON-able (format sama dengan data_loader)."""
    p = emiten.profil
    out: dict[str, Any] = {
        "profil": {
            "kode": p.kode, "nama": p.nama, "sektor": p.sektor,
            "sub_sektor": p.sub_sektor, "deskripsi_bisnis": p.deskripsi_bisnis,
            "manajemen": p.manajemen, "keunggulan_kompetitif": p.keunggulan_kompetitif,
            "prospek_industri": p.prospek_industri, "berita_terkini": p.berita_terkini,
        },
        "laporan": [
            {
                "tahun": l.tahun,
                "total_aset": l.total_aset, "aset_lancar": l.aset_lancar,
                "total_liabilitas": l.total_liabilitas,
                "liabilitas_lancar": l.liabilitas_lancar,
                "total_ekuitas": l.total_ekuitas,
                "pendapatan": l.pendapatan, "laba_kotor": l.laba_kotor,
                "laba_operasi": l.laba_operasi, "laba_bersih": l.laba_bersih,
                "arus_kas_operasi": l.arus_kas_operasi,
                "arus_kas_investasi": l.arus_kas_investasi,
                "arus_kas_pendanaan": l.arus_kas_pendanaan,
            }
            for l in emiten.laporan_urut()
        ],
    }
    if emiten.pasar:
        m = emiten.pasar
        out["pasar"] = {
            "harga_saham": m.harga_saham, "saham_beredar": m.saham_beredar,
            "per_sektor": m.per_sektor, "pbv_sektor": m.pbv_sektor,
            "mean_per_3y": m.mean_per_3y, "mean_pbv_3y": m.mean_pbv_3y,
            "growth_rate": m.growth_rate, "discount_rate": m.discount_rate,
            "terminal_growth": m.terminal_growth, "tahun_proyeksi": m.tahun_proyeksi,
            "dividend_yield": m.dividend_yield,
            "dividen_per_saham": m.dividen_per_saham,
            "dividen_beruntun": m.dividen_beruntun,
        }
    return out
