"""Helper skema JSON untuk output terstruktur tiap pilar."""

from __future__ import annotations

from typing import Any


def poin_skor(deskripsi: str) -> dict[str, Any]:
    """Skema satu poin penilaian: skor 1-10 + justifikasi singkat."""
    return {
        "type": "object",
        "properties": {
            "skor": {
                "type": "integer",
                "description": f"Skor 1-10 untuk {deskripsi}",
            },
            "justifikasi": {
                "type": "string",
                "description": f"Justifikasi singkat (1-3 kalimat) untuk {deskripsi}",
            },
        },
        "required": ["skor", "justifikasi"],
        "additionalProperties": False,
    }


def skema_pilar(poin: dict[str, str], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bangun skema objek untuk satu pilar.

    poin: {nama_field: deskripsi} untuk tiap poin ber-skor.
    extra: properti tambahan (mis. ringkasan/status) beserta skemanya.
    """
    props: dict[str, Any] = {k: poin_skor(v) for k, v in poin.items()}
    required = list(poin.keys())

    if extra:
        props.update(extra)
        required.extend(extra.keys())

    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }
