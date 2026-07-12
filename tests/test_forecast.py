import unittest

from draftnest.forecast import proyeksi_tahun_depan
from draftnest.models import Emiten, ProfilEmiten
from tests.fixtures import emiten_contoh, laporan


class TestForecast(unittest.TestCase):
    def test_proyeksi_dasar(self):
        pr = proyeksi_tahun_depan(emiten_contoh(), n_tahun=3)
        self.assertEqual(len(pr.proyeksi), 3)
        self.assertEqual([p.tahun for p in pr.proyeksi], [2025, 2026, 2027])
        # CAGR pendapatan 67000 -> 72000 selama 1 tahun
        self.assertAlmostEqual(pr.cagr_pendapatan, (72000 / 67000) - 1, places=6)
        # Tahun pertama = terakhir * (1 + CAGR)
        self.assertAlmostEqual(
            pr.proyeksi[0].pendapatan, 72000 * (1 + pr.cagr_pendapatan), places=4
        )
        # Margin proyeksi = laba/pendapatan proyeksi
        p0 = pr.proyeksi[0]
        self.assertAlmostEqual(p0.net_margin, p0.laba_bersih / p0.pendapatan, places=6)

    def test_kurang_data_kosong(self):
        e = Emiten(
            profil=ProfilEmiten(kode="X", nama="X", sektor="s"),
            laporan=[laporan(2024)],  # hanya 1 tahun
            pasar=None,
        )
        pr = proyeksi_tahun_depan(e)
        self.assertEqual(pr.proyeksi, [])
        self.assertIsNone(pr.cagr_pendapatan)


if __name__ == "__main__":
    unittest.main()
