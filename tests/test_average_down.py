import unittest

from draftnest.average_down import Pembelian, hitung, lot_untuk_target


class TestAverageDown(unittest.TestCase):
    def test_contoh_excel(self):
        # Posisi awal 34 lot @718, average down 4x lot (136) @655. Harga kini 655.
        beli = [Pembelian(lot=34, harga=718), Pembelian(lot=136, harga=655)]
        h = hitung(beli, harga_sekarang=655, cash=10_000_000)
        self.assertEqual(h.total_lot, 170)
        self.assertEqual(h.total_saham, 17000)
        # modal = 34*100*718 + 136*100*655 = 2.441.200 + 8.908.000 = 11.349.200
        self.assertAlmostEqual(h.total_modal, 11_349_200)
        self.assertAlmostEqual(h.harga_rata, 11_349_200 / 17000, places=4)  # ~667.6
        # rugi = 17000*655 - 11.349.200 = 11.135.000 - 11.349.200 = -214.200
        self.assertAlmostEqual(h.untung_rugi, -214_200)
        self.assertTrue(h.di_bawah_rata)  # 655 < ~667.6
        self.assertEqual(h.risiko, "HIGH RISK")  # 11.3jt/10jt > 0.7

    def test_bep_dan_untung(self):
        beli = [Pembelian(lot=10, harga=1000)]
        h = hitung(beli, harga_sekarang=1200)
        self.assertAlmostEqual(h.harga_rata, 1000)
        self.assertAlmostEqual(h.untung_rugi, 10 * 100 * 200)  # +200.000
        self.assertAlmostEqual(h.untung_rugi_pct, 0.2)
        self.assertFalse(h.di_bawah_rata)
        # kenaikan ke BEP dari harga sekarang: (1000-1200)/1200 negatif (sudah di atas)
        self.assertAlmostEqual(h.kenaikan_ke_bep_pct, (1000 - 1200) / 1200)

    def test_risiko_tingkat(self):
        beli = [Pembelian(lot=10, harga=1000)]  # modal 1.000.000
        self.assertEqual(hitung(beli, 1000, cash=1_000_000).risiko, "HIGH RISK")   # 1.0
        self.assertEqual(hitung(beli, 1000, cash=2_000_000).risiko, "MEDIUM RISK")  # 0.5
        self.assertEqual(hitung(beli, 1000, cash=5_000_000).risiko, "LOW RISK")     # 0.2
        self.assertIsNone(hitung(beli, 1000).risiko)  # tanpa cash

    def test_lot_untuk_target(self):
        # Awal 10 lot @1000 (avg 1000). Beli @800, target avg 900.
        # q = (900*1000 - 1000*1000)/(800-900) = (-100000)/(-100) = 1000 saham = 10 lot
        lot = lot_untuk_target(10, 1000, 800, 900)
        self.assertAlmostEqual(lot, 10)
        # verifikasi: 10 lot awal + 10 lot @800 -> avg
        h = hitung([Pembelian(10, 1000), Pembelian(10, 800)], 800)
        self.assertAlmostEqual(h.harga_rata, 900)

    def test_lot_untuk_target_tak_valid(self):
        # target di atas avg awal / harga beli di atas target -> None
        self.assertIsNone(lot_untuk_target(10, 1000, 800, 1100))  # target > avg
        self.assertIsNone(lot_untuk_target(10, 1000, 950, 900))   # harga_beli > target


if __name__ == "__main__":
    unittest.main()
