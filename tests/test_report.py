import unittest

from draftnest.report import jalankan_analisis
from tests.fixtures import emiten_contoh


class FakeClient:
    """Stub ClaudeClient: mengembalikan skor tetap berdasar isi skema."""

    def __init__(self, skor=8):
        self.skor = skor

    def analisis(self, system, prompt, schema):
        props = schema["properties"]
        out = {}
        for k, v in props.items():
            if v.get("type") == "object" and "skor" in v.get("properties", {}):
                out[k] = {"skor": self.skor, "justifikasi": "tes"}
        # field ekstra
        if "status" in props:
            out["status"] = "undervalued"
        if "ringkasan" in props:
            out["ringkasan"] = "ringkasan tes"
        if "kesimpulan_valuasi" in props:
            out["kesimpulan_valuasi"] = "kesimpulan tes"
        return out


class TestReport(unittest.TestCase):
    def test_offline_tanpa_client(self):
        h = jalankan_analisis(emiten_contoh(), None)
        # Tanpa LLM: KETIGA pilar kini diberi skor deterministik dari data.
        self.assertIsNotNone(h.skor_pilar["kualitatif"])
        self.assertIsNotNone(h.skor_pilar["kuantitatif"])
        self.assertIsNotNone(h.skor_pilar["valuasi"])
        # Skor akhir terhitung -> ada rekomendasi Beli/Tahan/Jual
        self.assertIsNotNone(h.skor_akhir)
        self.assertRegex(h.rekomendasi, r"BELI|TAHAN|JUAL")
        # Rasio, valuasi, & ramalan harga deterministik tetap terisi
        self.assertIsNotNone(h.kuantitatif_data)
        self.assertIsNotNone(h.valuasi_data)
        self.assertIsNotNone(h.ramalan_harga)

    def test_skor_tinggi_beli(self):
        h = jalankan_analisis(emiten_contoh(), FakeClient(skor=9))
        self.assertAlmostEqual(h.skor_pilar["kualitatif"], 9)
        self.assertAlmostEqual(h.skor_pilar["kuantitatif"], 9)
        self.assertAlmostEqual(h.skor_pilar["valuasi"], 9)
        self.assertAlmostEqual(h.skor_akhir, 9)
        self.assertEqual(h.rekomendasi, "BELI")

    def test_skor_rendah_jual(self):
        h = jalankan_analisis(emiten_contoh(), FakeClient(skor=3))
        self.assertAlmostEqual(h.skor_akhir, 3)
        self.assertEqual(h.rekomendasi, "JUAL")

    def test_overvalued_menurunkan_beli(self):
        # skor 8 (>=7.5 = BELI) + status overvalued -> diturunkan jadi TAHAN
        class OverClient(FakeClient):
            def analisis(self, system, prompt, schema):
                out = super().analisis(system, prompt, schema)
                if "status" in schema["properties"]:
                    out["status"] = "overvalued"
                return out

        h = jalankan_analisis(emiten_contoh(), OverClient(skor=8))
        self.assertIn("TAHAN", h.rekomendasi)


if __name__ == "__main__":
    unittest.main()
