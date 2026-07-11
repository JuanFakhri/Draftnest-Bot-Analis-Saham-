"""Antarmuka baris perintah Draftnest.

Contoh:
  python -m draftnest data/ICBP.json
  python -m draftnest data/ICBP.json --output laporan_ICBP.md
  python -m draftnest data/ICBP.json --offline     # tanpa panggilan LLM
"""

from __future__ import annotations

import argparse
import os
import sys

from .client import ClaudeClient
from .data_loader import muat_emiten
from .formatter import format_markdown
from .report import jalankan_analisis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="draftnest",
        description="Bot analisis saham IDX berbasis 3 pilar "
        "(Kualitatif, Kuantitatif, Valuasi).",
    )
    parser.add_argument("emiten", help="Path file JSON emiten (mis. data/ICBP.json).")
    parser.add_argument("-o", "--output", help="Simpan laporan Markdown ke file.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Jangan panggil Claude API; hanya olah data kuantitatif & valuasi.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model Claude (default: claude-opus-4-8 / env DRAFTNEST_MODEL).",
    )
    args = parser.parse_args(argv)

    try:
        emiten = muat_emiten(args.emiten)
    except (OSError, ValueError) as e:
        print(f"Gagal memuat emiten: {e}", file=sys.stderr)
        return 1

    client = None
    if not args.offline:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(
                "Peringatan: ANTHROPIC_API_KEY tidak diset. Menjalankan mode --offline "
                "(analisis LLM dilewati). Set key atau gunakan --offline untuk "
                "menyembunyikan pesan ini.",
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
