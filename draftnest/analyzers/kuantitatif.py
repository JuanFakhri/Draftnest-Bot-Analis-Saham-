"""Pilar 2 — Analisis Kuantitatif (interpretasi LLM atas rasio).

Rasio dihitung deterministik di `ratios.py`, lalu Claude menginterpretasi &
memberi skor pada 4 dimensi: profitabilitas, solvabilitas, likuiditas,
pertumbuhan.
"""

from __future__ import annotations

from typing import Any, Optional

from ..client import ClaudeClient
from ..ratios import RasioKunci, RingkasanKuantitatif
from ._schema import skema_pilar

SYSTEM = (
    "Anda analis keuangan kuantitatif untuk saham IDX. Interpretasikan rasio "
    "keuangan secara ketat dan berbasis angka. Jawab dalam Bahasa Indonesia."
)

SKEMA = skema_pilar(
    {
        "profitabilitas": "profitabilitas (ROE, ROA, margin)",
        "solvabilitas": "solvabilitas/leverage (DER)",
        "likuiditas": "likuiditas (Current Ratio)",
        "pertumbuhan": "pertumbuhan pendapatan & laba",
    },
    extra={
        "ringkasan": {
            "type": "string",
            "description": "Ringkasan naratif 2-4 kalimat atas kesehatan kuantitatif.",
        }
    },
)


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x: Optional[float]) -> str:
    return f"{x:.2f}x" if x is not None else "n/a"


def _baris_rasio(r: RasioKunci) -> str:
    return (
        f"  {r.tahun}: ROE {_pct(r.roe)}, ROA {_pct(r.roa)}, DER {_num(r.der)}, "
        f"CR {_num(r.current_ratio)}, NPM {_pct(r.net_profit_margin)}, "
        f"GPM {_pct(r.gross_profit_margin)}, OPM {_pct(r.operating_margin)}"
    )


def _prompt(kode: str, ringkasan: RingkasanKuantitatif) -> str:
    historis = "\n".join(_baris_rasio(r) for r in ringkasan.rasio_historis)
    return f"""Interpretasikan rasio keuangan emiten {kode} berikut (hasil olahan dari
Neraca, Laba Rugi, dan Arus Kas). Tahun data: {ringkasan.tahun_data}.

Rasio historis:
{historis}

Pertumbuhan (CAGR):
  Pendapatan : {_pct(ringkasan.growth_pendapatan)}
  Laba bersih: {_pct(ringkasan.growth_laba_bersih)}

Beri skor 1-10 (10 terbaik) + justifikasi untuk tiap dimensi: profitabilitas,
solvabilitas, likuiditas, dan pertumbuhan. Kaitkan skor dengan angka konkret dan
konteks wajar untuk sektor di IDX."""


def analisis_kuantitatif_llm(
    client: ClaudeClient, kode: str, ringkasan: RingkasanKuantitatif
) -> dict[str, Any]:
    return client.analisis(SYSTEM, _prompt(kode, ringkasan), SKEMA)
