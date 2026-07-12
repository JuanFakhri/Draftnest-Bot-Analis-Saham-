"""Format HasilAnalisis menjadi laporan Markdown yang mudah dibaca."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from .ratios import RasioKunci
from .report import HasilAnalisis


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x: Optional[float]) -> str:
    return f"{x:.2f}x" if x is not None else "n/a"


def _rp(x: Optional[float]) -> str:
    return f"Rp{x:,.0f}" if x is not None else "n/a"


def _skor(x: Optional[float]) -> str:
    return f"{x:.1f}/10" if x is not None else "n/a"


def _poin_llm(hasil: Optional[dict[str, Any]], field: str, judul: str) -> str:
    if not hasil or field not in hasil:
        return f"- **{judul}:** _(analisis LLM tidak tersedia)_"
    p = hasil[field]
    return f"- **{judul} — {p['skor']}/10:** {p['justifikasi']}"


def _tabel_rasio(rasio: list[RasioKunci]) -> str:
    head = "| Tahun | ROE | ROA | DER | Current Ratio | Net Margin |\n"
    head += "|---|---|---|---|---|---|\n"
    baris = [
        f"| {r.tahun} | {_pct(r.roe)} | {_pct(r.roa)} | {_num(r.der)} | "
        f"{_num(r.current_ratio)} | {_pct(r.net_profit_margin)} |"
        for r in rasio
    ]
    return head + "\n".join(baris)


def format_markdown(h: HasilAnalisis) -> str:
    p = h.emiten.profil
    L: list[str] = []

    L.append(f"# Analisis Saham — {p.nama} ({p.kode})")
    L.append(f"_Sektor: {p.sektor}{(' / ' + p.sub_sektor) if p.sub_sektor else ''} · "
             f"Tanggal analisis: {date.today().isoformat()}_")
    L.append("")

    # --- Kesimpulan ---
    L.append("## Kesimpulan")
    L.append(f"- **Rekomendasi:** {h.rekomendasi}")
    L.append(f"- **Skor akhir:** {_skor(h.skor_akhir)}")
    L.append(f"- **Skor Kualitatif:** {_skor(h.skor_pilar['kualitatif'])} · "
             f"**Kuantitatif:** {_skor(h.skor_pilar['kuantitatif'])} · "
             f"**Valuasi:** {_skor(h.skor_pilar['valuasi'])}")
    if h.valuasi_llm:
        L.append(f"- **Status valuasi:** {h.valuasi_llm.get('status', 'n/a')}")
    L.append("")

    # --- Pilar 1: Kualitatif ---
    L.append("## 1. Analisis Kualitatif")
    L.append(_poin_llm(h.kualitatif_llm, "model_bisnis", "Model Bisnis"))
    L.append(_poin_llm(h.kualitatif_llm, "manajemen", "Manajemen"))
    L.append(_poin_llm(h.kualitatif_llm, "keunggulan_kompetitif", "Keunggulan Kompetitif"))
    L.append(_poin_llm(h.kualitatif_llm, "prospek_industri", "Prospek Industri"))
    if h.kualitatif_llm and h.kualitatif_llm.get("ringkasan"):
        L.append("")
        L.append(f"> {h.kualitatif_llm['ringkasan']}")
    L.append("")

    # --- Pilar 2: Kuantitatif ---
    L.append("## 2. Analisis Kuantitatif")
    L.append("### Data Olahan (rasio kunci)")
    L.append(_tabel_rasio(h.kuantitatif_data.rasio_historis))
    L.append("")
    L.append(f"- Pertumbuhan pendapatan (CAGR): {_pct(h.kuantitatif_data.growth_pendapatan)}")
    L.append(f"- Pertumbuhan laba bersih (CAGR): {_pct(h.kuantitatif_data.growth_laba_bersih)}")
    L.append("")
    L.append("### Penilaian")
    L.append(_poin_llm(h.kuantitatif_llm, "profitabilitas", "Profitabilitas"))
    L.append(_poin_llm(h.kuantitatif_llm, "solvabilitas", "Solvabilitas"))
    L.append(_poin_llm(h.kuantitatif_llm, "likuiditas", "Likuiditas"))
    L.append(_poin_llm(h.kuantitatif_llm, "pertumbuhan", "Pertumbuhan"))
    if h.kuantitatif_llm and h.kuantitatif_llm.get("ringkasan"):
        L.append("")
        L.append(f"> {h.kuantitatif_llm['ringkasan']}")
    L.append("")

    # --- Pilar 3: Valuasi ---
    L.append("## 3. Analisis Valuasi")
    if h.valuasi_data:
        v = h.valuasi_data
        r = v.relative
        a = v.absolute
        L.append("### Relative Valuation")
        L.append(f"- Harga pasar: {_rp(v.harga_saham)} · EPS: {_rp(r.eps)} · BVPS: {_rp(r.bvps)}")
        L.append(f"- PER: {_num(r.per)} (sektor {_num(r.per_sektor)}) · "
                 f"PBV: {_num(r.pbv)} (sektor {_num(r.pbv_sektor)})")
        L.append(f"- Harga wajar (PER sektor): {_rp(r.harga_wajar_per)} · "
                 f"(PBV sektor): {_rp(r.harga_wajar_pbv)}")
        L.append("")
        L.append("### Absolute Valuation (DCF)")
        L.append(f"- Asumsi: growth {_pct(a.growth_rate)}, discount {_pct(a.discount_rate)}, "
                 f"terminal {_pct(a.terminal_growth)}, {a.tahun_proyeksi} tahun")
        L.append(f"- Nilai intrinsik: {_rp(a.nilai_intrinsik_per_saham)} per lembar")
        L.append(f"- Margin of safety: {_pct(v.margin_of_safety)}")
        L.append("")
        L.append("### Penilaian")
        L.append(_poin_llm(h.valuasi_llm, "relative_valuation", "Relative Valuation"))
        L.append(_poin_llm(h.valuasi_llm, "absolute_valuation", "Absolute Valuation"))
        if h.valuasi_llm and h.valuasi_llm.get("kesimpulan_valuasi"):
            L.append("")
            L.append(f"> {h.valuasi_llm['kesimpulan_valuasi']}")
    else:
        L.append("_Data pasar tidak tersedia — valuasi dilewati._")
    L.append("")

    # --- Disclaimer ---
    L.append("---")
    L.append("_Disclaimer: Analisis ini dihasilkan otomatis untuk tujuan edukasi/riset "
             "dan **bukan** rekomendasi jual/beli. Selalu lakukan riset mandiri (DYOR). "
             "Hasil DCF sangat sensitif terhadap asumsi._")

    return "\n".join(L)
