"""Eksperimen backtest Strategi 3 (BSJP Optimized Screener) + varian.

Strategi 3 (dari panduan pengguna):
  Momentum : Change% > 3, Last > MA5, Last >= Open (candle hijau)
  Volume   : Volume > 2x Volume-MA20, Volume > Volume kemarin
  Aman     : Value > Rp5 M, harga kemarin > 60
  (cek manual: close near high, RSI < 80, foreign flow — sebagian dikodekan)

Menguji S3 dan variannya vs benchmark S2-produksi (MA5>MA20), split TRAIN/TEST,
plus ekspektasi bersih setelah biaya. Murni analitik, TIDAK menulis docs/data.

Jalankan (GitHub Actions, butuh Yahoo):
  python -m draftnest.experiment_s3
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


def make_filter_s3(change_min=0.03, need_green=True, vol_mult_ma20=2.0,
                   need_vol_gt_prev=True, val_min=5e9, price_min=60.0,
                   rsi_max=None, near_high=None, ma5_above_ma20=False):
    """Predikat S3. ctx=(opens,highs,lows,closes,vols,sma5,sma20,vma20,rsis,shares)."""
    def f(i, ctx) -> bool:
        opens, highs, lows, closes, vols, sma5, sma20, vma20, rsis, shares = ctx
        if i < 1 or closes[i - 1] <= 0 or vols[i - 1] <= 0:
            return False
        change = (closes[i] - closes[i - 1]) / closes[i - 1]
        if change <= change_min:                          # naik > 3%
            return False
        if sma5[i] is None or closes[i] <= sma5[i]:        # Last > MA5
            return False
        if need_green and closes[i] < opens[i]:            # Last >= Open (hijau)
            return False
        if vma20[i] is None or vols[i] <= vol_mult_ma20 * vma20[i]:  # Vol > 2x MA20
            return False
        if need_vol_gt_prev and vols[i] <= vols[i - 1]:    # Vol > Vol kemarin
            return False
        if closes[i] * vols[i] < val_min:                  # Value > Rp5 M
            return False
        if closes[i - 1] <= price_min:                     # harga kemarin > 60
            return False
        if rsi_max is not None and (rsis[i] is None or rsis[i] > rsi_max):
            return False
        if near_high is not None:
            rng = highs[i] - lows[i]
            if rng > 0 and (highs[i] - closes[i]) / rng > near_high:  # close dekat high
                return False
        if ma5_above_ma20 and (sma5[i] is None or sma20[i] is None or sma5[i] < sma20[i]):
            return False
        return True
    return f


# Benchmark: S2 produksi saat ini (Momentum quiet-volume + MA5>MA20).
def _filter_s2_skrg(i, ctx) -> bool:
    opens, highs, lows, closes, vols, sma5, sma20, vma20, rsis, shares = ctx
    if i < 1 or closes[i - 1] <= 0 or vols[i - 1] <= 0:
        return False
    if closes[i] <= 1.05 * closes[i - 1]:
        return False
    if sma5[i] is None or closes[i] < sma5[i]:
        return False
    if vols[i] >= 1.2 * vols[i - 1]:
        return False
    if closes[i] * vols[i] < 5e9:
        return False
    if sma5[i] is None or sma20[i] is None or sma5[i] < sma20[i]:
        return False
    return True


VARIAN = {
    "S3 base (rumus)":           make_filter_s3(),
    "S3 change>5%":              make_filter_s3(change_min=0.05),
    "S3 + RSI<80":               make_filter_s3(rsi_max=80.0),
    "S3 + close-near-high":      make_filter_s3(near_high=0.30),
    "S3 + RSI<80 + near-high":   make_filter_s3(rsi_max=80.0, near_high=0.30),
    "S3 + MA5>MA20":             make_filter_s3(ma5_above_ma20=True),
    "S3 vol>3x MA20":            make_filter_s3(vol_mult_ma20=3.0),
    "[benchmark] S2 skrg":       _filter_s2_skrg,
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


def evaluasi_emiten(opens, highs, lows, closes, vols, shares, stat):
    n = len(closes)
    if n < 30 or shares <= 0:
        return
    sma5 = sma(closes, 5)
    sma20 = sma(closes, 20)
    vma20 = sma(vols, 20)
    rsis = rsi(closes, 14)
    ctx = (opens, highs, lows, closes, vols, sma5, sma20, vma20, rsis, shares)
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
    print(f"[exp-s3] menguji {len(VARIAN)} varian pada {len(universe)} emiten "
          f"(biaya {BIAYA*100:.2f}%/PP, split 70/30)", file=sys.stderr)

    stat = {nama: {"train": _akun(), "test": _akun()} for nama in VARIAN}
    ok = gagal = 0
    for idx, (kode, saham) in enumerate(universe, 1):
        tkr = yf.Ticker(f"{kode}.JK")
        hist = _safe(lambda: tkr.history(period="6y"))
        if hist is None or getattr(hist, "empty", True) or "Open" not in hist or "High" not in hist:
            gagal += 1
        else:
            try:
                opens = [float(x) for x in hist["Open"].tolist()]
                highs = [float(x) for x in hist["High"].tolist()]
                lows = [float(x) for x in hist["Low"].tolist()]
                closes = [float(x) for x in hist["Close"].tolist()]
                vols = [float(x) for x in hist["Volume"].tolist()]
                evaluasi_emiten(opens, highs, lows, closes, vols, saham, stat)
                ok += 1
            except Exception as e:
                gagal += 1
                print(f"[gagal] {kode}: {e}", file=sys.stderr)
        if idx % 100 == 0:
            print(f"[exp-s3] {idx}/{len(universe)} (ok {ok}, gagal {gagal})", file=sys.stderr)
        if delay:
            time.sleep(delay)

    baris = [_baris(nama, stat[nama]["train"], stat[nama]["test"]) for nama in VARIAN]
    baris.sort(key=lambda b: b["test_win"], reverse=True)

    print(f"\n[exp-s3] selesai: {ok} emiten sukses, {gagal} gagal.\n", file=sys.stderr)
    print("===EXPERIMENT_S3_BEGIN===")
    hdr = (f"{'Varian':<26} {'TrainWin':>8} {'TestWin':>8} {'TestGain':>9} "
           f"{'Test>=3%':>9} {'NetSemalam':>11} {'TestN':>7}")
    print(hdr)
    print("-" * len(hdr))
    for b in baris:
        print(f"{b['nama']:<26} {b['train_win']*100:>7.1f}% {b['test_win']*100:>7.1f}% "
              f"{b['test_ov']*100:>8.2f}% {b['test_h3']*100:>8.1f}% "
              f"{b['test_net']*100:>10.2f}% {b['test_n']:>7}")
    print("===EXPERIMENT_S3_END===")
    print("===EXPERIMENT_S3_JSON===")
    print(json.dumps({"emiten_ok": ok, "biaya": BIAYA, "hasil": baris}, ensure_ascii=False))
    print("===EXPERIMENT_S3_JSON_END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
