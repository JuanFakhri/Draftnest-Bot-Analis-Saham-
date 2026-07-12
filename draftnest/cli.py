"""Antarmuka baris perintah Draftnest.

Analisis dari file JSON:
  python -m draftnest data/ICBP.json
  python -m draftnest data/ICBP.json --output laporan_ICBP.md
  python -m draftnest data/ICBP.json --offline

Ambil data otomatis dari IDX (profil/harga) + XBRL (laporan keuangan):
  python -m draftnest --fetch ICBP --xbrl instance_2024.xbrl --save-json data/ICBP.json
  python -m draftnest --fetch ICBP --xbrl 2023.xbrl --xbrl 2024.xbrl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import ClaudeClient
from .data_loader import muat_emiten
from .formatter import format_markdown
from .report import jalankan_analisis


def _emiten_dari_argumen(args: argparse.Namespace):
    """Kembalikan objek Emiten dari --fetch/--xbrl atau dari file JSON."""
    if args.fetch:
        from .idx_scraper import IDXError, bangun_emiten

        try:
            emiten = bangun_emiten(
                args.fetch,
                xbrl_files=args.xbrl or None,
                tahun=args.year,
                ambil_pasar=not args.no_market,
            )
        except IDXError as e:
            print(f"Gagal mengambil data IDX: {e}", file=sys.stderr)
            raise SystemExit(1)

        if args.save_json:
            from .idx_scraper import emiten_ke_dict

            with open(args.save_json, "w", encoding="utf-8") as f:
                json.dump(emiten_ke_dict(emiten), f, ensure_ascii=False, indent=2)
            print(f"Data emiten disimpan ke {args.save_json}", file=sys.stderr)
        return emiten

    if not args.emiten:
        print("Sertakan file JSON emiten atau gunakan --fetch KODE.", file=sys.stderr)
        raise SystemExit(2)

    return muat_emiten(args.emiten)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="draftnest",
        description="Bot analisis saham IDX berbasis 3 pilar "
        "(Kualitatif, Kuantitatif, Valuasi).",
    )
    parser.add_argument("emiten", nargs="?", help="Path file JSON emiten (mis. data/ICBP.json).")
    parser.add_argument("-o", "--output", help="Simpan laporan Markdown ke file.")
    parser.add_argument(
        "--offline", action="store_true",
        help="Jangan panggil Claude API; hanya olah data kuantitatif & valuasi.",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override model Claude (default: claude-opus-4-8 / env DRAFTNEST_MODEL).",
    )
    # Opsi pengambilan data IDX.
    parser.add_argument("--fetch", metavar="KODE", help="Ambil data emiten dari IDX (mis. ICBP).")
    parser.add_argument(
        "--xbrl", action="append", metavar="FILE",
        help="File XBRL instance laporan keuangan IDX (boleh diulang untuk banyak tahun).",
    )
    parser.add_argument("--year", type=int, help="Override tahun buku untuk XBRL.")
    parser.add_argument(
        "--no-market", action="store_true",
        help="Jangan ambil harga/saham dari IDX (lengkapi manual).",
    )
    parser.add_argument("--save-json", metavar="FILE", help="Simpan data emiten hasil fetch ke JSON.")
    args = parser.parse_args(argv)

    try:
        emiten = _emiten_dari_argumen(args)
    except SystemExit as e:
        return int(e.code or 1)
    except (OSError, ValueError) as e:
        print(f"Gagal memuat emiten: {e}", file=sys.stderr)
        return 1

    client = None
    if not args.offline:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(
                "Peringatan: ANTHROPIC_API_KEY tidak diset. Menjalankan mode --offline "
                "(analisis LLM dilewati).",
                file=sys.stderr,
            )
        else:
            try:
                client = ClaudeClient(model=args.model) if args.model else ClaudeClient()
            except Exception as e:  # pragma: no cover - init error
                print(f"Gagal inisialisasi Claude: {e}", file=sys.stderr)
                return 1

    try:
        hasil = jalankan_analisis(emiten, client)
    except Exception as e:
        print(f"Gagal menjalankan analisis: {e}", file=sys.stderr)
        return 1

    laporan = format_markdown(hasil)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(laporan)
            print(f"Laporan disimpan ke {args.output}")
        except OSError as e:
            print(f"Gagal menyimpan laporan: {e}", file=sys.stderr)
            return 1
    else:
        print(laporan)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
