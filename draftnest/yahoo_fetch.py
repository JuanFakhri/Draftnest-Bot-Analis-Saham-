"""Ambil data emiten IDX (profil, 5 tahun laporan, harga) via yfinance.

Dipakai oleh pipeline server-side (GitHub Actions) — bukan di browser.
yfinance menangani crumb/cookie Yahoo yang tak bisa dilakukan dari halaman
statis, sehingga jalur ini andal untuk laporan keuangan multi-tahun.

Butuh: pip install yfinance  (lihat requirements-data.txt)
"""

from __future__ import annotations

from typing import Any, Optional

from .models import DataPasar, Emiten, LaporanTahunan, ProfilEmiten

# Kandidat label baris yfinance -> field LaporanTahunan.
# yfinance memakai label berbeda antar versi/emiten; coba berurutan.
_INCOME = {
    "pendapatan": ["Total Revenue", "Operating Revenue"],
    "laba_kotor": ["Gross Profit"],
    "laba_operasi": ["Operating Income", "Total Operating Income As Reported"],
    "laba_bersih": ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"],
}
_BALANCE = {
    "total_aset": ["Total Assets"],
    "aset_lancar": ["Current Assets", "Total Current Assets"],
    "total_liabilitas": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "liabilitas_lancar": ["Current Liabilities", "Total Current Liabilities"],
    "total_ekuitas": ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"],
}
_CASHFLOW = {
    "arus_kas_operasi": ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"],
    "arus_kas_investasi": ["Investing Cash Flow", "Total Cashflows From Investing Activities"],
    "arus_kas_pendanaan": ["Financing Cash Flow", "Total Cash From Financing Activities"],
    "free_cash_flow": ["Free Cash Flow"],
}


def _pick(df, kandidat: list[str], kolom) -> Optional[float]:
    """Ambil nilai pertama yang cocok dari DataFrame yfinance (index=label)."""
    if df is None or getattr(df, "empty", True):
        return None
    for label in kandidat:
        if label in df.index:
            try:
                v = df.loc[label, kolom]
            except Exception:
                continue
            if v is not None and not _isnan(v):
                return float(v)
    return None


def _isnan(v: Any) -> bool:
    try:
        return v != v  # NaN != NaN
    except Exception:
        return False


def fetch_emiten(kode: str, tahun_maks: int = 5) -> Emiten:
    """Ambil Emiten lengkap dari Yahoo untuk kode IDX (mis. 'ICBP')."""
    import yfinance as yf  # impor lazy

    kode = kode.upper()
    tkr = yf.Ticker(f"{kode}.JK")

    info: dict[str, Any] = {}
    try:
        info = tkr.info or {}
    except Exception:
        info = {}

    profil = ProfilEmiten(
        kode=kode,
        nama=info.get("longName") or info.get("shortName") or kode,
        sektor=info.get("sector", "") or "",
        sub_sektor=info.get("industry", "") or "",
        deskripsi_bisnis=info.get("longBusinessSummary", "") or "",
    )

    income = _safe(lambda: tkr.income_stmt)
    balance = _safe(lambda: tkr.balance_sheet)
    cashflow = _safe(lambda: tkr.cashflow)

    # Kolom = periode (Timestamp), terbaru dulu. Ambil hingga `tahun_maks`.
    kolom = []
    for df in (income, balance, cashflow):
        if df is not None and not getattr(df, "empty", True):
            kolom = list(df.columns)
            break

    laporan: list[LaporanTahunan] = []
    for col in kolom[:tahun_maks]:
        tahun = getattr(col, "year", None)
        if tahun is None:
            continue
        lap = LaporanTahunan(
            tahun=int(tahun),
            total_aset=_pick(balance, _BALANCE["total_aset"], col) or 0.0,
            aset_lancar=_pick(balance, _BALANCE["aset_lancar"], col) or 0.0,
            total_liabilitas=_pick(balance, _BALANCE["total_liabilitas"], col) or 0.0,
            liabilitas_lancar=_pick(balance, _BALANCE["liabilitas_lancar"], col) or 0.0,
            total_ekuitas=_pick(balance, _BALANCE["total_ekuitas"], col) or 0.0,
            pendapatan=_pick(income, _INCOME["pendapatan"], col) or 0.0,
            laba_kotor=_pick(income, _INCOME["laba_kotor"], col) or 0.0,
            laba_operasi=_pick(income, _INCOME["laba_operasi"], col) or 0.0,
            laba_bersih=_pick(income, _INCOME["laba_bersih"], col) or 0.0,
            arus_kas_operasi=_pick(cashflow, _CASHFLOW["arus_kas_operasi"], col) or 0.0,
            arus_kas_investasi=_pick(cashflow, _CASHFLOW["arus_kas_investasi"], col) or 0.0,
            arus_kas_pendanaan=_pick(cashflow, _CASHFLOW["arus_kas_pendanaan"], col) or 0.0,
            free_cash_flow=_pick(cashflow, _CASHFLOW["free_cash_flow"], col),
        )
        laporan.append(lap)

    pasar: Optional[DataPasar] = None
    harga = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    saham = info.get("sharesOutstanding")
    if harga and saham:
        pasar = DataPasar(
            harga_saham=float(harga),
            saham_beredar=float(saham),
            per_sektor=None,   # rata-rata sektor tak tersedia dari Yahoo; isi manual
            pbv_sektor=None,
        )

    if not laporan and pasar is None:
        raise RuntimeError(
            f"Yahoo tidak mengembalikan data untuk {kode}.JK. Kode salah, "
            f"tidak terdaftar, atau rate-limit."
        )

    return Emiten(profil=profil, laporan=laporan, pasar=pasar)


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None
