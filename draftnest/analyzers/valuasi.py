"""Pilar 3 — Analisis Valuasi (interpretasi LLM atas hasil hitung).

PER/PBV (relative) & DCF (absolute) dihitung deterministik di `valuation.py`.
Claude menilai apakah saham undervalued/fair/overvalued + skor tiap jalur.
"""

from __future__ import annotations

from typing import Any, Optional

from typing import Optional

from ..client import ClaudeClient
from ..forecast import HasilProyeksi
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
        "outlook_tahun_depan": {
            "type": "string",
            "description": "Outlook 2-4 kalimat untuk tahun-tahun mendatang berdasarkan "
            "proyeksi tren + prospek, termasuk risiko utama terhadap proyeksi.",
        },
    },
)


def _teks_proyeksi(proyeksi: Optional[HasilProyeksi]) -> str:
    if not proyeksi or not proyeksi.proyeksi:
        return "(proyeksi tak tersedia — butuh >= 2 tahun data)"
    baris = [
        f"  {p.tahun}: pendapatan ~{p.pendapatan:,.0f}, laba bersih ~{p.laba_bersih:,.0f}, "
        f"margin ~{(p.net_margin * 100):.1f}%" if p.net_margin is not None else
        f"  {p.tahun}: pendapatan ~{p.pendapatan:,.0f}, laba bersih ~{p.laba_bersih:,.0f}"
        for p in proyeksi.proyeksi
    ]
    return (
        f"CAGR pendapatan {_pct(proyeksi.cagr_pendapatan)}, CAGR laba {_pct(proyeksi.cagr_laba)}\n"
        + "\n".join(baris)
    )


def _rp(x: Optional[float]) -> str:
    return f"Rp{x:,.0f}" if x is not None else "n/a"


def _num(x: Optional[float]) -> str:
    return f"{x:.2f}x" if x is not None else "n/a"


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _prompt(kode: str, v: HasilValuasi, proyeksi: Optional[HasilProyeksi]) -> str:
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
Fair Value (Mean PER&PBV): Mean PER {_num(r.mean_per)} x EPS -> {_rp(r.fair_value_per)}; Mean PBV {_num(r.mean_pbv)} x BVPS -> {_rp(r.fair_value_pbv)}; Fair Value {_rp(r.fair_value)} (MoS {_pct(r.mos_fair_value)})

== Absolute Valuation (DCF) ==
FCF dasar        : {a.fcf_dasar:,.0f}
Asumsi           : growth {_pct(a.growth_rate)}, discount {_pct(a.discount_rate)}, terminal {_pct(a.terminal_growth)}, proyeksi {a.tahun_proyeksi} thn
Enterprise value : {a.enterprise_value:,.0f}
Nilai intrinsik  : {_rp(a.nilai_intrinsik_per_saham)} per lembar
Margin of safety : {_pct(v.margin_of_safety)} (positif = harga di bawah nilai intrinsik)

== Proyeksi Tahun Mendatang (ekstrapolasi CAGR) ==
{_teks_proyeksi(proyeksi)}

Beri skor 1-10 (10 = paling menarik / paling undervalued) + justifikasi untuk
relative_valuation dan absolute_valuation. Tentukan status: undervalued /
fairvalued / overvalued. Isi 'outlook_tahun_depan' dengan pandangan ke depan
berdasar proyeksi di atas plus risiko utamanya. Ingatkan bila DCF/proyeksi
sangat sensitif terhadap asumsi."""


def analisis_valuasi_llm(
    client: ClaudeClient, kode: str, v: HasilValuasi,
    proyeksi: Optional[HasilProyeksi] = None,
) -> dict[str, Any]:
    return client.analisis(SYSTEM, _prompt(kode, v, proyeksi), SKEMA)
