import unittest

from draftnest import telegram_bot as tb
from tests.fixtures import emiten_contoh


class TestPesanBuilder(unittest.TestCase):
    def test_start_help(self):
        self.assertIn("Draftnest", tb.pesan_start())
        self.assertIn("/screener", tb.pesan_help())

    def test_analisis(self):
        em = emiten_contoh()
        em.pasar.mean_per_3y = 15.0
        teks = tb.pesan_analisis(em)
        self.assertIn("ICBP", teks)
        self.assertRegex(teks, r"BELI|TAHAN|JUAL")
        self.assertIn("Skor akhir", teks)

    def test_screener(self):
        data = [
            {"kode": "AAA", "nama": "Alpha", "naik_pendapatan": True, "naik_laba": True,
             "prospek_bagus": True, "skor_akhir": 8.0, "dividend_yield": 0.05},
            {"kode": "BBB", "nama": "Beta", "naik_pendapatan": False, "naik_laba": True,
             "prospek_bagus": True, "skor_akhir": 7.0},
        ]
        teks = tb.pesan_screener(data)
        self.assertIn("AAA", teks)
        self.assertNotIn("BBB", teks)   # tak lolos (pendapatan tak naik)

    def test_dividen_urut(self):
        data = [
            {"kode": "AAA", "nama": "A", "dividend_yield": 0.04},
            {"kode": "BBB", "nama": "B", "dividend_yield": 0.09, "dividen_beruntun": 3},
            {"kode": "CCC", "nama": "C"},  # tanpa dividen -> tak masuk
        ]
        teks = tb.pesan_dividen(data)
        self.assertLess(teks.index("BBB"), teks.index("AAA"))  # yield lebih tinggi di atas
        self.assertNotIn("CCC", teks)

    def test_bsjp(self):
        data = [{"kode": "AAA", "nama": "A", "strat2_sinyal": True, "bsjp_peluang": 0.3}]
        bt = {"strategi": {"s2": {"win_rate": 0.64, "rata_overnight": 0.014, "peluang_3persen": 0.14}}}
        teks = tb.pesan_bsjp(data, bt, "s2")
        self.assertIn("AAA", teks)
        self.assertIn("64.0%", teks)
        self.assertIn("gap-down", teks)

    def test_cari(self):
        idx = [{"kode": "BBCA", "nama": "Bank Central Asia"},
               {"kode": "TLKM", "nama": "Telkom"}]
        self.assertIn("BBCA", tb.pesan_cari(idx, "bank"))
        self.assertNotIn("TLKM", tb.pesan_cari(idx, "bank"))
        self.assertIn("cocok", tb.pesan_cari(idx, "xyz"))


class TestPelangganScan(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig = tb.SUBS_FILE
        from pathlib import Path
        tb.SUBS_FILE = Path(self._tmp.name)

    def tearDown(self):
        import os
        tb.SUBS_FILE = self._orig
        os.unlink(self._tmp.name)

    def test_langganan_roundtrip(self):
        tb.simpan_pelanggan({111, 222})
        self.assertEqual(tb.muat_pelanggan(), {111, 222})

    def test_ringkasan_scan_bentuk(self):
        teks = tb.ringkasan_scan()   # baca screener.json repo
        self.assertIn("Scan BSJP", teks)
        self.assertIn("Momentum", teks)


class TestDispatch(unittest.TestCase):
    def test_routing_tanpa_disk(self):
        self.assertIn("Draftnest", tb.tangani_pesan("/start"))
        self.assertIn("Bantuan", tb.tangani_pesan("/help"))
        self.assertIn("tak dikenal", tb.tangani_pesan("/perintahaneh xyz"))

    def test_perintah_dengan_suffix_bot(self):
        # /help@NamaBot harus tetap dikenali di grup
        self.assertIn("Bantuan", tb.tangani_pesan("/help@DraftnestBot"))

    def test_analisis_format_kosong(self):
        self.assertIn("Format", tb.tangani_pesan("/analisis"))


if __name__ == "__main__":
    unittest.main()
