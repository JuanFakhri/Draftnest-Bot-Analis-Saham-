"""Ambil data emiten IDX (profil, 5 tahun laporan, harga) via yfinance.

Dipakai oleh pipeline server-side (GitHub Actions) — bukan di browser.
yfinance menangani crumb/cookie Yahoo yang tak bisa dilakukan dari halaman
statis, sehingga jalur ini andal untuk laporan keuangan multi-tahun.

Butuh: pip install yfinance  (lihat requirements-data.txt)
"""

from __future__ import annotations

from typing import Any, Optional

from .models import DataPasar, Emiten, LaporanTahunan, ProfilEmiten, StatistikHarian

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

    # Deteksi ketidaksesuaian mata uang: banyak emiten IDX (mis. POWR) melaporkan
    # keuangan dalam USD sementara harga dalam IDR. Rasio (ROE/ROA/margin) tetap
    # valid, tetapi valuasi per-saham (EPS/PER/PBV/DCF) jadi tidak akurat.
    fin_cur = (info.get("financialCurrency") or "").upper()
    price_cur = (info.get("currency") or "").upper()
    catatan = ""
    if fin_cur and price_cur and fin_cur != price_cur:
        catatan = (
            f"⚠️ Laporan keuangan dalam {fin_cur}, harga dalam {price_cur}. "
            f"Rasio (ROE/ROA/margin) tetap valid, tetapi valuasi per-saham "
            f"(EPS/PER/PBV/DCF) tidak akurat tanpa konversi kurs."
        )

    profil = ProfilEmiten(
        kode=kode,
        nama=info.get("longName") or info.get("shortName") or kode,
        sektor=info.get("sector", "") or "",
        sub_sektor=info.get("industry", "") or "",
        deskripsi_bisnis=info.get("longBusinessSummary", "") or "",
        berita_terkini=catatan,
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
        # Lewati tahun "hantu" (kolom ada di satu statement tetapi nilainya kosong)
        # — mis. tahun tertua yfinance yang semua angka intinya nol.
        if lap.total_aset == 0 and lap.pendapatan == 0 and lap.total_ekuitas == 0:
            continue
        laporan.append(lap)

    pasar: Optional[DataPasar] = None
    harga = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    saham = info.get("sharesOutstanding")
    harian: Optional[StatistikHarian] = None
    backtest: Optional[dict] = None
    if harga and saham:
        hist = _safe(lambda: tkr.history(period="6y"))  # sekali tarik, dipakai ulang
        mean_per, mean_pbv = _mean_per_pbv(laporan, float(saham), hist, n=3)
        div_yield, div_ps, div_streak = _dividen(tkr, float(harga), info)
        harian = _bsjp_stats(hist)
        backtest = _backtest(hist, float(saham))
        pasar = DataPasar(
            harga_saham=float(harga),
            saham_beredar=float(saham),
            per_sektor=None,   # rata-rata sektor tak tersedia dari Yahoo; isi manual
            pbv_sektor=None,
            mean_per_3y=mean_per,
            mean_pbv_3y=mean_pbv,
            dividend_yield=div_yield,
            dividen_per_saham=div_ps,
            dividen_beruntun=div_streak,
        )

    if not laporan and pasar is None:
        raise RuntimeError(
            f"Yahoo tidak mengembalikan data untuk {kode}.JK. Kode salah, "
            f"tidak terdaftar, atau rate-limit."
        )

    return Emiten(profil=profil, laporan=laporan, pasar=pasar,
                  harian=harian, backtest=backtest)


def fetch_sinyal(kode: str, saham: float) -> Optional[dict]:
    """Ambil HANYA riwayat harga harian lalu hitung ulang sinyal & statistik.

    Jauh lebih ringan dari `fetch_emiten` (tak menarik laporan keuangan/info),
    dipakai untuk refresh sinyal BSJP harian. `saham` diambil dari data lama.
    Kembalikan {"harga", "harian"(dict), "backtest"(dict)} atau None bila gagal.
    """
    import yfinance as yf
    from dataclasses import asdict

    tkr = yf.Ticker(f"{kode.upper()}.JK")
    hist = _safe(lambda: tkr.history(period="6y"))
    if hist is None or getattr(hist, "empty", True) or "Close" not in hist or not len(hist):
        return None
    try:
        harga = float(hist["Close"].iloc[-1])
    except Exception:
        harga = None
    harian = _bsjp_stats(hist)
    backtest = _backtest(hist, saham) if saham else None
    return {
        "harga": harga,
        "harian": asdict(harian) if harian else None,
        "backtest": backtest,
    }


def _backtest(hist, saham: float):
    """Backtest 2 strategi dari riwayat harga harian. None bila data kurang."""
    if hist is None or getattr(hist, "empty", True):
        return None
    if "Open" not in hist or "Close" not in hist or "Volume" not in hist:
        return None
    try:
        from .backtest import jalankan_backtest
        opens = [float(x) for x in hist["Open"].tolist()]
        closes = [float(x) for x in hist["Close"].tolist()]
        vols = [float(x) for x in hist["Volume"].tolist()]
        return jalankan_backtest(opens, closes, vols, saham)
    except Exception:
        return None


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _dividen(tkr, harga: float, info: dict):
    """Yield dividen 12 bln terakhir + jumlah tahun beruntun membagi dividen.

    Kembalikan (yield_fraksi, dividen_per_saham_12bln, tahun_beruntun).
    Prioritas dari histori `tkr.dividends` (paling akurat); fallback ke
    `info['dividendYield']`. None/0 bila tak membagi dividen.
    """
    div_ps = None
    streak = 0
    try:
        divs = tkr.dividends  # pandas Series indexed by tanggal pembayaran
        if divs is not None and not divs.empty:
            import pandas as pd  # noqa: F401  (yfinance sudah menariknya)
            per_tahun: dict[int, float] = {}
            for idx, val in divs.items():
                per_tahun[int(idx.year)] = per_tahun.get(int(idx.year), 0.0) + float(val)
            # Dividen per saham 12 bln terakhir = total tahun kalender terakhir yg ada.
            if per_tahun:
                tahun_terakhir = max(per_tahun)
                div_ps = per_tahun.get(tahun_terakhir)
                # Hitung beruntun mundur dari tahun terakhir (izinkan mulai dari
                # tahun lalu bila tahun berjalan belum bagikan).
                mulai = tahun_terakhir
                t = mulai
                while per_tahun.get(t, 0.0) > 0:
                    streak += 1
                    t -= 1
    except Exception:
        div_ps = None

    div_yield = (div_ps / harga) if (div_ps and harga) else None
    # Fallback yield dari info bila histori kosong.
    if div_yield is None:
        raw = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
        if raw:
            # Yahoo kadang memberi 8.0 (persen) kadang 0.08 (fraksi).
            div_yield = raw / 100.0 if raw > 1 else float(raw)
    return div_yield, div_ps, streak


def _bsjp_stats(hist, target: float = 0.03, lookback: int = 252) -> Optional[StatistikHarian]:
    """Statistik overnight gap (close[t-1] -> open[t]) untuk strategi BSJP.

    "Beli Sore, Jual Pagi": beli di harga penutupan, jual di pembukaan besok.
    Return per hari = (Open[t] - Close[t-1]) / Close[t-1]. Dihitung atas
    `lookback` hari terakhir (default ~1 tahun bursa). None bila data kurang.
    """
    if hist is None or getattr(hist, "empty", True):
        return None
    if "Open" not in hist or "Close" not in hist:
        return None
    try:
        h = hist.tail(lookback + 1)
        opens = [float(x) for x in h["Open"].tolist()]
        closes = [float(x) for x in h["Close"].tolist()]
        vols = [float(x) for x in h["Volume"].tolist()] if "Volume" in h else []
        gaps = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev and prev > 0 and opens[i] and opens[i] > 0:
                gaps.append((opens[i] - prev) / prev)
    except Exception:
        return None

    n = len(gaps)
    if n < 30:  # sampel terlalu kecil untuk bermakna
        return None
    rata = sum(gaps) / n
    urut = sorted(gaps)
    median = urut[n // 2] if n % 2 else (urut[n // 2 - 1] + urut[n // 2]) / 2
    positif = [g for g in gaps if g > 0]
    var = sum((g - rata) ** 2 for g in gaps) / (n - 1)
    return StatistikHarian(
        sampel_hari=n,
        peluang_naik_target=sum(1 for g in gaps if g >= target) / n,
        win_rate=len(positif) / n,
        rata_gap=rata,
        median_gap=median,
        rata_gap_positif=(sum(positif) / len(positif)) if positif else None,
        volatilitas_gap=var ** 0.5,
        volume_rata=(sum(vols) / len(vols)) if vols else None,
        target=target,
    )


def _mean_per_pbv(laporan, saham: float, hist, n: int = 3):
    """Rata-rata PER & PBV `n` tahun terakhir dari harga historis Yahoo.

    Pendekatan: harga rata-rata per tahun kalender (mean close) dibagi EPS/BVPS
    tahun itu. Saham beredar diasumsikan tetap (aproksimasi wajar). None bila
    data tak cukup. `hist` = DataFrame riwayat harga (sudah ditarik di luar).
    """
    if not laporan or saham <= 0:
        return None, None
    try:
        if hist is None or getattr(hist, "empty", True) or "Close" not in hist:
            return None, None
        close = hist["Close"]
        harga_per_tahun = {int(idx.year): float(val) for idx, val in close.groupby(close.index.year).mean().items()}
    except Exception:
        return None, None

    pers, pbvs = [], []
    for lap in sorted(laporan, key=lambda x: x.tahun, reverse=True)[:n]:
        harga_th = harga_per_tahun.get(lap.tahun)
        if not harga_th:
            continue
        eps = lap.laba_bersih / saham
        bvps = lap.total_ekuitas / saham
        if eps > 0:
            pers.append(harga_th / eps)
        if bvps > 0:
            pbvs.append(harga_th / bvps)

    mean_per = sum(pers) / len(pers) if pers else None
    mean_pbv = sum(pbvs) / len(pbvs) if pbvs else None
    return mean_per, mean_pbv
