"""Pipeline pra-ambil data emiten -> file JSON untuk website.

Membaca daftar kode (watchlist / seluruh IDX), mengambil data via yfinance
(tanpa API key), dan menulis docs/data/<kode>.json + index.json. Dijalankan
GitHub Actions (server-side), lalu commit ke repo agar website auto-isi instan.

Pemakaian:
  python -m draftnest.pipeline                      # pakai data/watchlist.txt
  python -m draftnest.pipeline BBCA BBRI TLKM       # kode eksplisit
  python -m draftnest.pipeline --all                # SELURUH emiten IDX
  python -m draftnest.pipeline --all --resume       # lewati yang sudah ada
  python -m draftnest.pipeline --all --list-only    # hanya cetak jumlah universe
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from .idx_scraper import emiten_ke_dict
from .idx_universe import FALLBACK_FILE, daftar_emiten

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "data" / "watchlist.txt"
OUT_DIR = ROOT / "docs" / "data"


def baca_watchlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    kode: list[str] = []
    for baris in path.read_text(encoding="utf-8").splitlines():
        b = baris.split("#", 1)[0].strip().upper()
        if b:
            kode.append(b)
    return kode


def jalankan(
    kode_list: list[str], out_dir: Path, resume: bool = False, delay: float = 0.4
) -> int:
    from .yahoo_fetch import fetch_emiten

    out_dir.mkdir(parents=True, exist_ok=True)
    indeks: list[dict[str, str]] = []
    gagal: list[str] = []
    dilewati = 0
    total = len(kode_list)

    for i, kode in enumerate(kode_list, 1):
        target = out_dir / f"{kode.lower()}.json"
        if resume and target.exists():
            dilewati += 1
            continue
        try:
            emiten = fetch_emiten(kode)
            target.write_text(
                json.dumps(emiten_ke_dict(emiten), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            indeks.append({"kode": kode, "nama": emiten.profil.nama})
            print(f"[{i}/{total}] [ok]   {kode}: {len(emiten.laporan)} tahun laporan")
        except Exception as e:
            gagal.append(kode)
            print(f"[{i}/{total}] [gagal] {kode}: {e}", file=sys.stderr)
        if delay:
            time.sleep(delay)

    _tulis_index(out_dir)
    _tulis_screener(out_dir)
    print(f"\nSelesai: {len(indeks)} sukses, {len(gagal)} gagal, {dilewati} dilewati.")
    # Sukses bila ada yang tertulis, atau semua memang sudah ada (resume).
    return 0 if (indeks or dilewati) else 1


def _tulis_index(out_dir: Path) -> None:
    """Bangun index.json dari seluruh file JSON emiten yang ada di out_dir."""
    emiten: list[dict[str, str]] = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            p = d.get("profil", {})
            if p.get("kode"):
                emiten.append({"kode": p["kode"], "nama": p.get("nama", p["kode"])})
        except Exception:
            continue
    (out_dir / "index.json").write_text(
        json.dumps(
            {"diperbarui": date.today().isoformat(), "emiten": emiten},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )


def _tulis_screener(out_dir: Path) -> None:
    """Bangun screener.json (ringkasan metrik semua emiten) untuk fitur Screener."""
    from .data_loader import muat_emiten
    from .screener import ringkas_emiten

    ringkasan: list[dict] = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name in ("index.json", "screener.json"):
            continue
        try:
            emiten = muat_emiten(f)
            if not emiten.laporan:
                continue
            ringkasan.append(ringkas_emiten(emiten))
        except Exception:
            continue
    (out_dir / "screener.json").write_text(
        json.dumps(
            {"diperbarui": date.today().isoformat(), "emiten": ringkasan},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"screener.json: {len(ringkasan)} emiten diringkas.")


def _refresh_fallback(kode_list: list[str]) -> None:
    """Simpan daftar universe ke data/idx_tickers.txt sebagai cache fallback."""
    if not kode_list:
        return
    header = (
        "# Cache daftar kode emiten IDX (fallback bila endpoint IDX tak terjangkau).\n"
        "# Diperbarui otomatis oleh pipeline --all.\n"
    )
    FALLBACK_FILE.write_text(header + "\n".join(sorted(set(kode_list))) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="draftnest.pipeline")
    ap.add_argument("kode", nargs="*", help="Kode emiten (default: data/watchlist.txt).")
    ap.add_argument("--all", action="store_true", help="Ambil SELURUH emiten IDX.")
    ap.add_argument("--resume", action="store_true", help="Lewati kode yang JSON-nya sudah ada.")
    ap.add_argument("--list-only", action="store_true", help="Hanya cetak jumlah universe, tanpa fetch.")
    ap.add_argument("--screener-only", action="store_true",
                    help="Regenerasi index.json & screener.json dari file yang ada, tanpa fetch.")
    ap.add_argument("--limit", type=int, default=0, help="Batasi jumlah kode (untuk uji).")
    ap.add_argument("--delay", type=float, default=0.4, help="Jeda antar-permintaan (detik).")
    ap.add_argument("--out", default=str(OUT_DIR), help="Direktori output JSON.")
    args = ap.parse_args(argv)

    if args.screener_only:
        out_dir = Path(args.out)
        _tulis_index(out_dir)
        _tulis_screener(out_dir)
        return 0

    if args.all:
        kode_list = daftar_emiten()
    elif args.kode:
        kode_list = [k.upper() for k in args.kode]
    else:
        kode_list = baca_watchlist(WATCHLIST)

    if not kode_list:
        print("Tidak ada kode emiten (universe kosong / watchlist kosong).", file=sys.stderr)
        return 2

    if args.limit and args.limit > 0:
        kode_list = kode_list[: args.limit]

    if args.list_only:
        print(f"Universe: {len(kode_list)} emiten IDX.")
        print("Contoh:", ", ".join(kode_list[:15]), "...")
        return 0

    # Segarkan cache fallback hanya bila universe IDX sungguh penuh (bukan fallback kecil).
    if args.all and len(kode_list) >= 100:
        _refresh_fallback(kode_list)

    return jalankan(kode_list, Path(args.out), resume=args.resume, delay=args.delay)


if __name__ == "__main__":
    raise SystemExit(main())
