"""Pilar 3 — Analisis Valuasi (interpretasi LLM atas hasil hitung).

PER/PBV (relative) & DCF (absolute) dihitung deterministik di `valuation.py`.
Claude menilai apakah saham undervalued/fair/overvalued + skor tiap jalur.
"""

from __future__ import annotations

from typing import Any, Optional

from ..client import ClaudeClient
from ..valuation import HasilValuasi
from ._schema import skema_pilar

SYSTEM = (
    "Anda analis valuasi saham IDX. Nilai kewajaran harga berdasarkan valuasi "
    "relatif (PER/PBV vs sektor) dan valuasi absolut (DCF). Bersikap konservatif "
    "dan sadar keterbatasan asumsi. Jawab dalam Bahasa Indonesia."
)

SKEMA = skema_pilar(
    {
        "relative_valuation": "kewajaran harga via PER/PBV dibanding sektor",
        "absolute_valuation": "kewajaran harga via DCF (nilai intrinsik)",
    },
    extra={
        "status": {
            "type": "string",
            "enum": ["undervalued", "fairvalued", "overvalued"],
            "description": "Kesimpulan status harga terhadap nilai wajar.",
        },
        "kesimpulan_valuasi": {
            "type": "string",
            "description": "Ringkasan 2-4 kalimat menggabungkan kedua jalur valuasi.",
        },
    },
)


def _rp(x: Optional[float]) -> str:
    return f"Rp{x:,.0f}" if x is not None else "n/a"


def _num(x: Optional[float]) -> str:
    return f"{x:.2f}x" if x is not None else "n/a"


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _prompt(kode: str, v: HasilValuasi) -> str:
    r = v.relative
    a = v.absolute
    return f"""Nilai kewajaran harga saham {kode}.
Harga pasar saat ini: {_rp(v.harga_saham)} per lembar.

== Relative Valuation ==
EPS         : {_rp(r.eps)}
BVPS        : {_rp(r.bvps)}
PER emiten  : {_num(r.per)}   | PER sektor: {_num(r.per_sektor)}
PBV emiten  : {_num(r.pbv)}   | PBV sektor: {_num(r.pbv_sektor)}
Harga wajar (PER sektor): {_rp(r.harga_wajar_per)}
Harga wajar (PBV sektor): {_rp(r.harga_wajar_pbv)}

== Absolute Valuation (DCF) ==
FCF dasar        : {a.fcf_dasar:,.0f}
Asumsi           : growth {_pct(a.growth_rate)}, discount {_pct(a.discount_rate)}, terminal {_pct(a.terminal_growth)}, proyeksi {a.tahun_proyeksi} thn
Enterprise value : {a.enterprise_value:,.0f}
Nilai intrinsik  : {_rp(a.nilai_intrinsik_per_saham)} per lembar
Margin of safety : {_pct(v.margin_of_safety)} (positif = harga di bawah nilai intrinsik)

Beri skor 1-10 (10 = paling menarik / paling undervalued) + justifikasi untuk
relative_valuation dan absolute_valuation. Tentukan status: undervalued /
fairvalued / overvalued. Ingatkan bila hasil DCF sangat sensitif terhadap asumsi."""


def analisis_valuasi_llm(client: ClaudeClient, kode: str, v: HasilValuasi) -> dict[str, Any]:
    return client.analisis(SYSTEM, _prompt(kode, v), SKEMA)
