import unittest

from draftnest import ratios as R
from tests.fixtures import emiten_contoh, laporan


class TestRasio(unittest.TestCase):
    def test_rasio_dasar(self):
        r = R.hitung_rasio(laporan(2024))
        self.assertAlmostEqual(r.roe, 9200 / 71000, places=6)
        self.assertAlmostEqual(r.roa, 9200 / 130000, places=6)
        self.assertAlmostEqual(r.der, 59000 / 71000, places=6)
        self.assertAlmostEqual(r.current_ratio, 46000 / 22000, places=6)
        self.assertAlmostEqual(r.net_profit_margin, 9200 / 72000, places=6)
        self.assertAlmostEqual(r.gross_profit_margin, 26000 / 72000, places=6)
        self.assertAlmostEqual(r.operating_margin, 15500 / 72000, places=6)

    def test_pembagian_nol_menghasilkan_none(self):
        r = R.hitung_rasio(laporan(2024, total_ekuitas=0, liabilitas_lancar=0))
        self.assertIsNone(r.roe)
        self.assertIsNone(r.der)
        self.assertIsNone(r.current_ratio)

    def test_cagr(self):
        # 100 -> 121 selama 2 tahun = 10% CAGR
        self.assertAlmostEqual(R._cagr(100, 121, 2), 0.1, places=6)
        self.assertIsNone(R._cagr(0, 121, 2))     # awal <= 0
        self.assertIsNone(R._cagr(100, 121, 0))   # periode <= 0
        self.assertIsNone(R._cagr(100, -5, 2))    # akhir <= 0

    def test_ringkasan_growth(self):
        ring = R.analisis_kuantitatif(emiten_contoh())
        self.assertEqual(ring.tahun_data, [2023, 2024])
        self.assertAlmostEqual(ring.growth_pendapatan, (72000 / 67000) - 1, places=6)
        self.assertAlmostEqual(ring.growth_laba_bersih, (9200 / 8000) - 1, places=6)
        self.assertEqual(ring.rasio_terbaru.tahun, 2024)


if __name__ == "__main__":
    unittest.main()
