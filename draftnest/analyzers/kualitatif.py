"""Pilar 1 — Analisis Kualitatif.

4 poin sesuai gambar: Model Bisnis, Manajemen, Keunggulan Kompetitif,
Prospek Industri. Model diminta memberi skor 1-10 + justifikasi tiap poin.
"""

from __future__ import annotations

from typing import Any

from ..client import ClaudeClient
from ..models import Emiten
from ._schema import skema_pilar

SYSTEM = (
    "Anda analis fundamental saham Bursa Efek Indonesia (IDX) yang objektif, "
    "kritis, dan berbasis bukti. Beri skor jujur; hindari optimisme berlebihan. "
    "Jawab dalam Bahasa Indonesia."
)

SKEMA = skema_pilar(
    {
        "model_bisnis": "kualitas & daya tahan model bisnis",
        "manajemen": "kompetensi & rekam jejak manajemen",
        "keunggulan_kompetitif": "moat / keunggulan kompetitif & pangsa pasar",
        "prospek_industri": "prospek pertumbuhan industri/sektor",
    },
    extra={
        "ringkasan": {
            "type": "string",
            "description": "Ringkasan naratif 2-4 kalimat atas keempat poin kualitatif.",
        }
    },
)


def _prompt(emiten: Emiten) -> str:
    p = emiten.profil
    return f"""Analisis kualitatif emiten berikut berdasarkan 4 poin.

Emiten : {p.nama} ({p.kode})
Sektor : {p.sektor} {('- ' + p.sub_sektor) if p.sub_sektor else ''}

1. Model Bisnis:
{p.deskripsi_bisnis or '(tidak ada data — nilai konservatif dan sebutkan keterbatasan data)'}

2. Manajemen:
{p.manajemen or '(tidak ada data)'}

3. Keunggulan Kompetitif:
{p.keunggulan_kompetitif or '(tidak ada data)'}

4. Prospek Industri:
{p.prospek_industri or '(tidak ada data)'}

Berita terkini:
{p.berita_terkini or '(tidak ada data)'}

Untuk tiap poin beri skor 1-10 (10 terbaik) dan justifikasi singkat.
Bila data tidak memadai, beri skor konservatif dan nyatakan keterbatasannya."""


def analisis_kualitatif(client: ClaudeClient, emiten: Emiten) -> dict[str, Any]:
    return client.analisis(SYSTEM, _prompt(emiten), SKEMA)
