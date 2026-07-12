"""Pembungkus tipis untuk Anthropic Claude API.

Setiap pilar mengirim prompt terpisah dan meminta output JSON terstruktur
(via output_config.format) sehingga skor & justifikasi mudah digabungkan.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MODEL = os.environ.get("DRAFTNEST_MODEL", "claude-opus-4-8")


class ClaudeClient:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        # Impor lazy agar mode --offline tidak butuh paket `anthropic`.
        import anthropic

        # Kredensial diambil dari environment (ANTHROPIC_API_KEY) atau
        # profil `ant auth login`. Jangan hardcode key.
        self.client = anthropic.Anthropic()
        self.model = model

    def analisis(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Kirim satu prompt pilar dan kembalikan hasil JSON tervalidasi."""
        resp = self.client.messages.create(
            model=self.model,
            # Cukup luang: token thinking (adaptive) ikut dihitung ke max_tokens.
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=system,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
            messages=[{"role": "user", "content": prompt}],
        )
        teks = next((b.text for b in resp.content if b.type == "text"), "")
        return json.loads(teks)
