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
        return f"- **{judul}:** _(belum bisa dinilai dari data yang tersedia)_"
    p = hasil[field]
    if p.get("skor") is None:
        return f"- **{judul}:** {p.get('justifikasi', 'belum bisa dinilai dari data')}"
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
        if r.fair_value is not None:
            L.append(f"- **Nilai wajar: {_rp(r.fair_value)}** (MoS {_pct(r.mos_fair_value)}) — "
                     f"metode: {r.metode_fair_value}")
        if r.fair_value is not None and r.mean_per is not None:
            L.append("")
            L.append("#### Fair Value (Mean PER & PBV)")
            L.append("| | | | |")
            L.append("|---|---|---|---|")
            L.append(f"| Mean P/E (3 Th) | {_num(r.mean_per)} | Fair Value P/E | {_rp(r.fair_value_per)} |")
            L.append(f"| EPS | {_rp(r.eps)} | Fair Value PBV | {_rp(r.fair_value_pbv)} |")
            L.append(f"| Mean PBV (3 Th) | {_num(r.mean_pbv)} | **Fair Value** | **{_rp(r.fair_value)}** |")
            L.append(f"| BVPS | {_rp(r.bvps)} | **Harga** | **{_rp(v.harga_saham)}** |")
            L.append(f"| | | **Margin of Safety** | **{_pct(r.mos_fair_value)}** |")
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

    # --- Proyeksi Tahun Mendatang ---
    if h.proyeksi_data and h.proyeksi_data.proyeksi:
        pr = h.proyeksi_data
        L.append("## 4. Proyeksi Tahun Mendatang")
        L.append(f"_Ekstrapolasi tren — CAGR pendapatan {_pct(pr.cagr_pendapatan)}, "
                 f"laba {_pct(pr.cagr_laba)}. Bukan ramalan pasti._")
        L.append("")
        L.append("| Tahun | Pendapatan (proy.) | Laba Bersih (proy.) | Net Margin |")
        L.append("|---|---|---|---|")
        for p in pr.proyeksi:
            L.append(f"| {p.tahun} | {p.pendapatan:,.0f} | {p.laba_bersih:,.0f} | {_pct(p.net_margin)} |")
        if h.valuasi_llm and h.valuasi_llm.get("outlook_tahun_depan"):
            L.append("")
            L.append(f"> {h.valuasi_llm['outlook_tahun_depan']}")
        L.append("")

    # --- Ramalan Harga Saham ---
    rh = h.ramalan_harga
    if rh:
        L.append("## 5. Ramalan Harga Saham")
        L.append(f"_Deterministik dari data (tanpa AI). Estimasi, bukan kepastian._")
        L.append("")
        L.append(f"- Harga sekarang: {_rp(rh.harga_sekarang)}")
        if rh.harga_wajar is not None:
            arah = "upside" if (rh.potensi_wajar_pct or 0) >= 0 else "downside"
            L.append(f"- **Nilai wajar sekarang: {_rp(rh.harga_wajar)}** "
                     f"({_pct(rh.potensi_wajar_pct)} {arah}) — {rh.metode_wajar}")
        if rh.target:
            L.append("")
            L.append(f"Target harga ke depan (EPS proyeksi × {_num(rh.multiple_pe)} — {rh.metode_multiple}):")
            L.append("")
            L.append("| Tahun | EPS (proy.) | Target Harga | Potensi vs Sekarang |")
            L.append("|---|---|---|---|")
            for t in rh.target:
                L.append(f"| {t.tahun} | {_rp(t.eps)} | {_rp(t.target_harga)} | {_pct(t.potensi_pct)} |")
            if rh.cagr_harga is not None:
                L.append("")
                L.append(f"- Perkiraan CAGR harga: **{_pct(rh.cagr_harga)}/tahun**")
        L.append("")

    # --- Disclaimer ---
    L.append("---")
    L.append("_Disclaimer: Analisis ini dihasilkan otomatis untuk tujuan edukasi/riset "
             "dan **bukan** rekomendasi jual/beli. Selalu lakukan riset mandiri (DYOR). "
             "Hasil DCF sangat sensitif terhadap asumsi._")

    return "\n".join(L)
