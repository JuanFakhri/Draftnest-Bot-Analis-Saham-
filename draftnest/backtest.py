"""Backtest strategi entry harian yang ditahan semalam (BSJP).

Dua strategi (dari permintaan pengguna) dievaluasi pada tiap hari bursa memakai
indikator dari harga harian; bila kondisi terpenuhi, posisi dibeli di harga
penutupan hari itu dan dijual di pembukaan hari berikutnya (overnight).

Keterbatasan jujur:
  - "Foreign Flow > 0" pada Strategi 1 TIDAK tersedia dari sumber data (yfinance)
    — itu data KSEI/broker. Syarat itu DILEWATI; hasil backtest jadi lebih longgar
    dari strategi aslinya.
  - Market cap memakai jumlah saham beredar SAAT INI untuk seluruh histori
    (aproksimasi; saham beredar dianggap tetap).

Semua fungsi murni (list angka) agar mudah diuji tanpa jaringan.
"""

from __future__ import annotations

from typing import Any, Optional

# Nama strategi untuk tampilan.
STRATEGI = {
    "s1": "RSI Pullback + Akumulasi (tanpa foreign flow)",
    "s2": "Momentum Breakout",
}


def rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """RSI Wilder. Elemen None sampai data cukup."""
    n = len(closes)
    out: list[Optional[float]] = [None] * n
    if n < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, n):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))

    def _rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - 100.0 / (1.0 + rs)

    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    out[period] = _rsi(avg_g, avg_l)
    for i in range(period + 1, n):
        avg_g = (avg_g * (period - 1) + gains[i - 1]) / period
        avg_l = (avg_l * (period - 1) + losses[i - 1]) / period
        out[i] = _rsi(avg_g, avg_l)
    return out


def sma(closes: list[float], period: int = 5) -> list[Optional[float]]:
    n = len(closes)
    out: list[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        out[i] = sum(closes[i - period + 1: i + 1]) / period
    return out


def _sinyal_s1(i, closes, vols, rsis, shares) -> bool:
    if i < 1 or rsis[i] is None or closes[i - 1] <= 0 or vols[i - 1] <= 0:
        return False
    if not (25.0 <= rsis[i] <= 50.0):
        return False
    if vols[i] < 2.0 * vols[i - 1]:               # 1 Day Volume Change >= 2x
        return False
    ret = (closes[i] - closes[i - 1]) / closes[i - 1]
    if not (-0.05 <= ret <= 0.01):                # return hari -5%..+1%
        return False
    if closes[i] < 100:
        return False
    if closes[i] * shares < 5e11:                 # market cap >= Rp500 M(iliar)
        return False
    if closes[i] * vols[i] < 1e9:                 # value >= Rp1 M(iliar)
        return False
    return True                                    # (foreign flow > 0 DILEWATI)


def _sinyal_s2(i, closes, vols, sma5, shares) -> bool:
    if i < 1 or closes[i - 1] <= 0 or vols[i - 1] <= 0:
        return False
    if closes[i] <= 1.05 * closes[i - 1]:         # naik > 5% dari kemarin
        return False
    if sma5[i] is None or closes[i] < sma5[i]:    # >= MA5
        return False
    if vols[i] >= 1.2 * vols[i - 1]:              # volume < 1.2x kemarin
        return False
    if closes[i] * vols[i] < 5e9:                 # value >= Rp5 M(iliar)
        return False
    return True


def _kosong() -> dict[str, Any]:
    return {"sinyal": 0, "menang": 0, "hit3": 0, "ret_total": 0.0, "sinyal_terakhir": False}


def jalankan_backtest(opens, closes, vols, shares) -> dict[str, Any]:
    """Backtest kedua strategi pada satu emiten. Kembalikan hitungan agregasi.

    Untuk tiap hari i yang memenuhi strategi (dan ada hari i+1), catat overnight
    return (open[i+1] - close[i]) / close[i]. `sinyal_terakhir` menandai apakah
    hari terakhir (i = n-1) memicu strategi (kandidat entri hari ini).
    """
    n = len(closes)
    hasil = {"s1": _kosong(), "s2": _kosong()}
    if n < 6 or shares <= 0:
        return hasil
    rsis = rsi(closes, 14)
    sma5 = sma(closes, 5)

    for i in range(1, n):
        s1 = _sinyal_s1(i, closes, vols, rsis, shares)
        s2 = _sinyal_s2(i, closes, vols, sma5, shares)
        if i == n - 1:
            hasil["s1"]["sinyal_terakhir"] = s1
            hasil["s2"]["sinyal_terakhir"] = s2
            continue  # hari terakhir tak punya i+1 untuk overnight
        for key, ok in (("s1", s1), ("s2", s2)):
            if not ok:
                continue
            if closes[i] <= 0:
                continue
            onr = (opens[i + 1] - closes[i]) / closes[i]
            h = hasil[key]
            h["sinyal"] += 1
            if onr > 0:
                h["menang"] += 1
            if onr >= 0.03:
                h["hit3"] += 1
            h["ret_total"] += onr
    return hasil


def agregasi(per_emiten: list[dict[str, Any]]) -> dict[str, Any]:
    """Gabungkan hitungan backtest banyak emiten -> statistik ringkas per strategi."""
    tot = {"s1": _kosong(), "s2": _kosong()}
    emiten_sinyal = {"s1": 0, "s2": 0}
    for bt in per_emiten:
        for k in ("s1", "s2"):
            b = bt.get(k)
            if not b:
                continue
            for f in ("sinyal", "menang", "hit3", "ret_total"):
                tot[k][f] += b.get(f, 0)
            if b.get("sinyal_terakhir"):
                emiten_sinyal[k] += 1

    out: dict[str, Any] = {}
    for k, nama in STRATEGI.items():
        s = tot[k]
        n = s["sinyal"]
        out[k] = {
            "nama": nama,
            "total_sinyal": n,
            "win_rate": (s["menang"] / n) if n else None,
            "peluang_3persen": (s["hit3"] / n) if n else None,
            "rata_overnight": (s["ret_total"] / n) if n else None,
            "emiten_sinyal_terakhir": emiten_sinyal[k],
        }
    return out
