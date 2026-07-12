"""Pipeline pra-ambil data emiten -> file JSON untuk website.

Membaca daftar kode (watchlist), mengambil data via yfinance, dan menulis
docs/data/<kode>.json + docs/data/index.json. Dijalankan oleh GitHub Actions
(server-side), lalu commit ke repo agar website bisa auto-isi instan.

Pemakaian:
  python -m draftnest.pipeline                      # pakai data/watchlist.txt
  python -m draftnest.pipeline BBCA BBRI TLKM       # kode eksplisit
  python -m draftnest.pipeline --out docs/data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .yahoo_fetch import fetch_emiten
from .idx_scraper import emiten_ke_dict

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


def jalankan(kode_list: list[str], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    indeks: list[dict[str, str]] = []
    gagal: list[str] = []

    for kode in kode_list:
        try:
            emiten = fetch_emiten(kode)
            d = emiten_ke_dict(emiten)
            (out_dir / f"{kode.lower()}.json").write_text(
                json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            indeks.append({"kode": kode, "nama": emiten.profil.nama})
            print(f"[ok]   {kode}: {len(emiten.laporan)} tahun laporan")
        except Exception as e:
            gagal.append(kode)
            print(f"[gagal] {kode}: {e}", file=sys.stderr)

    # Gabungkan dengan index lama agar kode yang tak di-refresh tetap terdaftar.
    idx_path = out_dir / "index.json"
    lama: dict[str, str] = {}
    if idx_path.exists():
        try:
            for e in json.loads(idx_path.read_text(encoding="utf-8")).get("emiten", []):
                lama[e["kode"]] = e["nama"]
        except Exception:
            pass
    for e in indeks:
        lama[e["kode"]] = e["nama"]

    idx_path.write_text(
        json.dumps(
            {
                "diperbarui": date.today().isoformat(),
                "emiten": [{"kode": k, "nama": v} for k, v in sorted(lama.items())],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nSelesai: {len(indeks)} sukses, {len(gagal)} gagal.")
    return 0 if indeks else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="draftnest.pipeline")
    ap.add_argument("kode", nargs="*", help="Kode emiten (default: baca data/watchlist.txt).")
    ap.add_argument("--out", default=str(OUT_DIR), help="Direktori output JSON.")
    args = ap.parse_args(argv)

    kode_list = [k.upper() for k in args.kode] or baca_watchlist(WATCHLIST)
    if not kode_list:
        print("Tidak ada kode emiten. Isi data/watchlist.txt atau beri argumen.", file=sys.stderr)
        return 2
    return jalankan(kode_list, Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
