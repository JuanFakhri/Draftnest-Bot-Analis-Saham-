"""Eksperimen A/B filter Strategi 2 (Momentum Breakout) BSJP.

Menguji BANYAK varian filter S2 sekaligus dalam SEKALI ambil histori harga,
lalu melaporkan win rate / rata gain semalam / peluang >=3% / ekspektasi bersih
setelah biaya, dipisah TRAIN (70% awal) vs TEST (30% akhir tiap deret) agar
ketahuan mana yang benar-benar unggul (bukan overfit ke masa lalu).

TIDAK menyentuh data produksi (docs/data tak ditulis) — hanya membaca daftar
emiten + saham beredar dari file yang ada, mengambil histori via yfinance, dan
mencetak tabel perbandingan. Dipakai lewat GitHub Actions (butuh Yahoo).

Jalankan:
  python -m draftnest.experiment_s2            # seluruh universe
  DRAFTNEST_EXP_LIMIT=150 python -m draftnest.experiment_s2   # batasi (uji cepat)
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

# Biaya bolak-balik (fee beli + fee & pajak jual + separuh spread), fraksi.
BIAYA = float(os.environ.get("DRAFTNEST_EXP_COST", "0.004"))


def make_filter(up_min=0.05, up_max=None, val_min=5e9, vol_ratio=1.2,
                price_min=0.0, need_ma20=False, rsi_max=None,
                need_prev_green=False, ma5_above_ma20=False):
    """Bangun predikat filter S2 berparameter. ctx = (closes,vols,sma5,sma20,rsis,shares)."""
    def f(i, ctx) -> bool:
        closes, vols, sma5, sma20, rsis, shares = ctx
        if i < 1 or closes[i - 1] <= 0 or vols[i - 1] <= 0:
            return False
        r = (closes[i] - closes[i - 1]) / closes[i - 1]
        if r <= up_min:                                   # naik minimal
            return False
        if up_max is not None and r > up_max:             # batas atas kenaikan
            return False
        if sma5[i] is None or closes[i] < sma5[i]:        # >= MA5
            return False
        if vols[i] >= vol_ratio * vols[i - 1]:            # volume tak melonjak
            return False
        if closes[i] * vols[i] < val_min:                 # likuiditas (value)
            return False
        if closes[i] < price_min:                         # harga minimal
            return False
        if need_ma20 and (sma20[i] is None or closes[i] < sma20[i]):
            return False
        if rsi_max is not None and (rsis[i - 1] is None or rsis[i - 1] >= rsi_max):
            return False
        if need_prev_green and (i < 2 or closes[i - 1] <= closes[i - 2]):
            return False
        if ma5_above_ma20 and (sma5[i] is None or sma20[i] is None or sma5[i] < sma20[i]):
            return False
        return True
    return f


# Daftar varian yang diuji (nama -> filter). "base" = S2 asli (target ~63.6%).
VARIAN = {
    "base (S2 asli)":            make_filter(),
    "cap kenaikan <=10%":        make_filter(up_max=0.10),
    "band 3-8%":                 make_filter(up_min=0.03, up_max=0.08),
    "band 4-7%":                 make_filter(up_min=0.04, up_max=0.07),
    "likuiditas >=Rp20M":        make_filter(val_min=20e9),
    "likuiditas >=Rp50M":        make_filter(val_min=50e9),
    "harga >=200":               make_filter(price_min=200.0),
    "volume < 1.0x":             make_filter(vol_ratio=1.0),
    "kemarin sudah hijau":       make_filter(need_prev_green=True),
    "MA5 > MA20":                make_filter(ma5_above_ma20=True),
    "likuid>=20M + cap<=10%":    make_filter(val_min=20e9, up_max=0.10),
    "MA20+RSI<70 (skrg)":        make_filter(need_ma20=True, rsi_max=70.0),
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
    """Akumulasi hasil semua varian utk satu emiten ke `stat` (train/test terpisah)."""
    n = len(closes)
    if n < 30 or shares <= 0:
        return
    sma5 = sma(closes, 5)
    sma20 = sma(closes, 20)
    rsis = rsi(closes, 14)
    ctx = (closes, vols, sma5, sma20, rsis, shares)
    potong = int(0.70 * n)               # 70% awal = train, sisanya test
    for i in range(1, n - 1):            # perlu i+1 utk overnight
        if closes[i] <= 0:
            continue
        onr = (opens[i + 1] - closes[i]) / closes[i]
        fase = "train" if i < potong else "test"
        for nama, filt in VARIAN.items():
            if filt(i, ctx):
                _rekam(stat[nama][fase], onr)


def _ambil_universe(limit=0):
    """(kode, saham_beredar) dari file emiten yang ada."""
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

    net = ov(te) - BIAYA               # ekspektasi bersih semalam di TEST
    return {
        "nama": nama,
        "train_n": tr["n"], "train_win": wr(tr),
        "test_n": te["n"], "test_win": wr(te), "test_ov": ov(te),
        "test_h3": h3(te), "test_net": net,
    }


def main() -> int:
    from .yahoo_fetch import _safe

    import yfinance as yf

    limit = int(os.environ.get("DRAFTNEST_EXP_LIMIT", "0") or 0)
    delay = float(os.environ.get("DRAFTNEST_EXP_DELAY", "0.3"))
    universe = _ambil_universe(limit)
    print(f"[exp] menguji {len(VARIAN)} varian S2 pada {len(universe)} emiten "
          f"(biaya {BIAYA*100:.2f}%/PP, split 70/30 train/test)", file=sys.stderr)

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
            print(f"[exp] {idx}/{len(universe)} (ok {ok}, gagal {gagal})", file=sys.stderr)
        if delay:
            time.sleep(delay)

    baris = [_baris(nama, stat[nama]["train"], stat[nama]["test"]) for nama in VARIAN]
    # Urutkan berdasar win rate di TEST (out-of-sample) menurun.
    baris.sort(key=lambda b: b["test_win"], reverse=True)

    print(f"\n[exp] selesai: {ok} emiten sukses, {gagal} gagal.\n", file=sys.stderr)
    # Tabel ringkas ke stdout (dengan penanda agar mudah diambil dari log).
    print("===EXPERIMENT_S2_BEGIN===")
    hdr = (f"{'Varian':<26} {'TrainWin':>8} {'TestWin':>8} {'TestGain':>9} "
           f"{'Test>=3%':>9} {'NetSemalam':>11} {'TestN':>7}")
    print(hdr)
    print("-" * len(hdr))
    for b in baris:
        print(f"{b['nama']:<26} {b['train_win']*100:>7.1f}% {b['test_win']*100:>7.1f}% "
              f"{b['test_ov']*100:>8.2f}% {b['test_h3']*100:>8.1f}% "
              f"{b['test_net']*100:>10.2f}% {b['test_n']:>7}")
    print("===EXPERIMENT_S2_END===")
    # JSON penuh juga, bila perlu diproses lebih lanjut.
    print("===EXPERIMENT_S2_JSON===")
    print(json.dumps({"emiten_ok": ok, "biaya": BIAYA, "hasil": baris}, ensure_ascii=False))
    print("===EXPERIMENT_S2_JSON_END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
