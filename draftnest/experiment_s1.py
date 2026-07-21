"""Eksperimen A/B filter Strategi 1 (RSI Pullback + Akumulasi) BSJP.

S1 asli win rate ~50% (praktis lempar koin, rugi setelah biaya). Modul ini
menguji BANYAK varian filter S1 sekaligus dalam SEKALI ambil histori harga,
dipisah TRAIN (70%) vs TEST (30%) agar ketahuan mana yang benar-benar unggul,
plus ekspektasi bersih setelah biaya. TIDAK menulis docs/data (murni analitik).

Jalankan (lewat GitHub Actions, butuh Yahoo):
  python -m draftnest.experiment_s1
  DRAFTNEST_EXP_LIMIT=150 python -m draftnest.experiment_s1   # uji cepat
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .backtest import rsi, sma

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"

BIAYA = float(os.environ.get("DRAFTNEST_EXP_COST", "0.004"))


def make_filter_s1(rsi_lo=25.0, rsi_hi=50.0, vol_mult=2.0, ret_lo=-0.05, ret_hi=0.01,
                   price_min=100.0, mktcap_min=5e11, val_min=1e9,
                   need_ma20=False, ma5_above_ma20=False, need_ma50=False):
    """Bangun predikat S1 berparameter. ctx=(closes,vols,sma5,sma20,sma50,rsis,shares)."""
    def f(i, ctx) -> bool:
        closes, vols, sma5, sma20, sma50, rsis, shares = ctx
        if i < 1 or rsis[i] is None or closes[i - 1] <= 0 or vols[i - 1] <= 0:
            return False
        if not (rsi_lo <= rsis[i] <= rsi_hi):             # zona RSI (oversold/pullback)
            return False
        if vols[i] < vol_mult * vols[i - 1]:              # lonjakan volume (akumulasi)
            return False
        ret = (closes[i] - closes[i - 1]) / closes[i - 1]
        if not (ret_lo <= ret <= ret_hi):                 # return hari ini
            return False
        if closes[i] < price_min:                         # harga minimal
            return False
        if closes[i] * shares < mktcap_min:               # market cap minimal
            return False
        if closes[i] * vols[i] < val_min:                 # likuiditas (value)
            return False
        if need_ma20 and (sma20[i] is None or closes[i] < sma20[i]):    # dip di uptrend
            return False
        if ma5_above_ma20 and (sma5[i] is None or sma20[i] is None or sma5[i] < sma20[i]):
            return False
        if need_ma50 and (sma50[i] is None or closes[i] < sma50[i]):    # uptrend panjang
            return False
        return True
    return f


# Varian S1 yang diuji. "base" = S1 asli (target ~50.4%).
VARIAN = {
    "base (S1 asli)":            make_filter_s1(),
    "RSI 30-45":                 make_filter_s1(rsi_lo=30.0, rsi_hi=45.0),
    "RSI 20-40 (dalam)":         make_filter_s1(rsi_lo=20.0, rsi_hi=40.0),
    "volume >=3x":               make_filter_s1(vol_mult=3.0),
    "pullback saja (ret<=0)":    make_filter_s1(ret_hi=0.0),
    "dip di uptrend (>MA20)":    make_filter_s1(need_ma20=True),
    "dip: MA5>MA20":             make_filter_s1(ma5_above_ma20=True),
    "dip: >MA50 (uptrend pjg)":  make_filter_s1(need_ma50=True),
    "likuid >=Rp5M":             make_filter_s1(val_min=5e9),
    "RSI30-45 + MA5>MA20":       make_filter_s1(rsi_lo=30.0, rsi_hi=45.0, ma5_above_ma20=True),
    "RSI30-45 + >MA20 + vol3x":  make_filter_s1(rsi_lo=30.0, rsi_hi=45.0, need_ma20=True, vol_mult=3.0),
    ">MA20 + vol3x + likuid5M":  make_filter_s1(need_ma20=True, vol_mult=3.0, val_min=5e9),
}


def _akun():
    return {"n": 0, "menang": 0, "hit3": 0, "ret": 0.0}


def _rekam(acc, onr):
    acc["n"] += 1
    if onr > 0:
        acc["menang"] += 1
    if onr >= 0.03:
        acc["hit3"] += 1
    acc["ret"] += onr


def evaluasi_emiten(opens, closes, vols, shares, stat):
    n = len(closes)
    if n < 60 or shares <= 0:      # butuh cukup data utk MA50
        return
    sma5 = sma(closes, 5)
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    rsis = rsi(closes, 14)
    ctx = (closes, vols, sma5, sma20, sma50, rsis, shares)
    potong = int(0.70 * n)
    for i in range(1, n - 1):
        if closes[i] <= 0:
            continue
        onr = (opens[i + 1] - closes[i]) / closes[i]
        fase = "train" if i < potong else "test"
        for nama, filt in VARIAN.items():
            if filt(i, ctx):
                _rekam(stat[nama][fase], onr)


def _ambil_universe(limit=0):
    out = []
    for f in sorted(DATA_DIR.glob("*.json")):
        if f.name in ("index.json", "screener.json", "backtest.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            kode = (d.get("profil") or {}).get("kode")
            saham = (d.get("pasar") or {}).get("saham_beredar")
            if kode and saham:
                out.append((kode, float(saham)))
        except Exception:
            continue
    if limit and limit > 0:
        out = out[:limit]
    return out


def _baris(nama, tr, te):
    def wr(a):
        return (a["menang"] / a["n"]) if a["n"] else 0.0

    def ov(a):
        return (a["ret"] / a["n"]) if a["n"] else 0.0

    def h3(a):
        return (a["hit3"] / a["n"]) if a["n"] else 0.0

    return {
        "nama": nama,
        "train_n": tr["n"], "train_win": wr(tr),
        "test_n": te["n"], "test_win": wr(te), "test_ov": ov(te),
        "test_h3": h3(te), "test_net": ov(te) - BIAYA,
    }


def main() -> int:
    from .yahoo_fetch import _safe
    import yfinance as yf

    limit = int(os.environ.get("DRAFTNEST_EXP_LIMIT", "0") or 0)
    delay = float(os.environ.get("DRAFTNEST_EXP_DELAY", "0.3"))
    universe = _ambil_universe(limit)
    print(f"[exp-s1] menguji {len(VARIAN)} varian S1 pada {len(universe)} emiten "
          f"(biaya {BIAYA*100:.2f}%/PP, split 70/30)", file=sys.stderr)

    stat = {nama: {"train": _akun(), "test": _akun()} for nama in VARIAN}
    ok = gagal = 0
    for idx, (kode, saham) in enumerate(universe, 1):
        tkr = yf.Ticker(f"{kode}.JK")
        hist = _safe(lambda: tkr.history(period="6y"))
        if hist is None or getattr(hist, "empty", True) or "Open" not in hist:
            gagal += 1
        else:
            try:
                opens = [float(x) for x in hist["Open"].tolist()]
                closes = [float(x) for x in hist["Close"].tolist()]
                vols = [float(x) for x in hist["Volume"].tolist()]
                evaluasi_emiten(opens, closes, vols, saham, stat)
                ok += 1
            except Exception as e:
                gagal += 1
                print(f"[gagal] {kode}: {e}", file=sys.stderr)
        if idx % 100 == 0:
            print(f"[exp-s1] {idx}/{len(universe)} (ok {ok}, gagal {gagal})", file=sys.stderr)
        if delay:
            time.sleep(delay)

    baris = [_baris(nama, stat[nama]["train"], stat[nama]["test"]) for nama in VARIAN]
    baris.sort(key=lambda b: b["test_win"], reverse=True)

    print(f"\n[exp-s1] selesai: {ok} emiten sukses, {gagal} gagal.\n", file=sys.stderr)
    print("===EXPERIMENT_S1_BEGIN===")
    hdr = (f"{'Varian':<28} {'TrainWin':>8} {'TestWin':>8} {'TestGain':>9} "
           f"{'Test>=3%':>9} {'NetSemalam':>11} {'TestN':>7}")
    print(hdr)
    print("-" * len(hdr))
    for b in baris:
        print(f"{b['nama']:<28} {b['train_win']*100:>7.1f}% {b['test_win']*100:>7.1f}% "
              f"{b['test_ov']*100:>8.2f}% {b['test_h3']*100:>8.1f}% "
              f"{b['test_net']*100:>10.2f}% {b['test_n']:>7}")
    print("===EXPERIMENT_S1_END===")
    print("===EXPERIMENT_S1_JSON===")
    print(json.dumps({"emiten_ok": ok, "biaya": BIAYA, "hasil": baris}, ensure_ascii=False))
    print("===EXPERIMENT_S1_JSON_END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
