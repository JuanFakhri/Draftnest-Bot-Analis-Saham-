import unittest

from draftnest import valuation as V
from draftnest.models import DataPasar, Emiten, ProfilEmiten
from tests.fixtures import emiten_contoh, laporan


class TestValuasi(unittest.TestCase):
    def test_relative(self):
        hasil = V.analisis_valuasi(emiten_contoh())
        r = hasil.relative
        self.assertAlmostEqual(r.eps, 9200 / 11.66, places=4)
        self.assertAlmostEqual(r.bvps, 71000 / 11.66, places=4)
        self.assertAlmostEqual(r.per, 11500 / (9200 / 11.66), places=4)
        self.assertAlmostEqual(r.pbv, 11500 / (71000 / 11.66), places=4)
        self.assertAlmostEqual(r.harga_wajar_per, 15.0 * (9200 / 11.66), places=4)
        self.assertAlmostEqual(r.harga_wajar_pbv, 3.0 * (71000 / 11.66), places=4)

    def test_dcf_konsisten(self):
        hasil = V.analisis_valuasi(emiten_contoh())
        a = hasil.absolute
        # FCF dasar = CFO + CFI = 12500 - 6000
        self.assertAlmostEqual(a.fcf_dasar, 6500, places=6)
        self.assertEqual(len(a.fcf_proyeksi), 5)
        # EV = sum(PV FCF) + PV terminal
        self.assertAlmostEqual(
            a.enterprise_value, sum(a.pv_fcf) + a.pv_terminal, places=4
        )
        # Nilai intrinsik = EV / saham beredar
        self.assertAlmostEqual(
            a.nilai_intrinsik_per_saham, a.enterprise_value / 11.66, places=4
        )
        # Margin of safety bertanda sesuai harga vs intrinsik
        expected_mos = (a.nilai_intrinsik_per_saham - 11500) / a.nilai_intrinsik_per_saham
        self.assertAlmostEqual(hasil.margin_of_safety, expected_mos, places=6)

    def test_dcf_growth_langkah_pertama(self):
        hasil = V.analisis_valuasi(emiten_contoh())
        a = hasil.absolute
        # FCF tahun-1 = FCF0 * (1 + growth)
        self.assertAlmostEqual(a.fcf_proyeksi[0], 6500 * 1.08, places=4)

    def test_terminal_fallback_saat_r_kurang_dari_gt(self):
        e = Emiten(
            profil=ProfilEmiten(kode="X", nama="X", sektor="s"),
            laporan=[laporan(2024)],
            pasar=DataPasar(harga_saham=100, saham_beredar=1,
                            discount_rate=0.02, terminal_growth=0.05),
        )
        a = V.analisis_valuasi(e).absolute
        # r <= gt -> pakai kelipatan konservatif 10x, bukan pembagian negatif
        self.assertAlmostEqual(a.terminal_value, a.fcf_proyeksi[-1] * 10, places=4)

    def test_fair_value_mean_per_pbv(self):
        # Studi kasus MAHA: EPS=19.1, BVPS=118.5, MeanPER=10.53, MeanPBV=1.79
        e = Emiten(
            profil=ProfilEmiten(kode="MAHA", nama="MAHA", sektor="s"),
            laporan=[laporan(2024, laba_bersih=19.1, total_ekuitas=118.5)],
            pasar=DataPasar(harga_saham=139, saham_beredar=1,
                            mean_per_3y=10.53, mean_pbv_3y=1.79),
        )
        r = V.analisis_valuasi(e).relative
        self.assertAlmostEqual(r.fair_value_per, 10.53 * 19.1, places=2)   # ~201.1
        self.assertAlmostEqual(r.fair_value_pbv, 1.79 * 118.5, places=2)   # ~212.1
        self.assertAlmostEqual(r.fair_value, (201.123 + 212.115) / 2, places=1)  # ~206.6
        self.assertAlmostEqual(r.mos_fair_value, (r.fair_value - 139) / r.fair_value, places=4)
        self.assertAlmostEqual(r.mos_fair_value, 0.327, places=2)          # ~32.7%

    def test_fair_value_hanya_satu_metode(self):
        # Hanya mean_pbv -> fair value = fair_value_pbv saja
        e = Emiten(
            profil=ProfilEmiten(kode="X", nama="X", sektor="s"),
            laporan=[laporan(2024)],
            pasar=DataPasar(harga_saham=100, saham_beredar=1, mean_pbv_3y=2.0),
        )
        r = V.analisis_valuasi(e).relative
        self.assertIsNone(r.fair_value_per)
        self.assertAlmostEqual(r.fair_value, r.fair_value_pbv, places=6)

    def test_tanpa_mean_pakai_fallback_justified(self):
        # Tanpa Mean PER/PBV & data sektor, nilai wajar tetap terisi via
        # fallback Justified P/B berbasis ROE (Gordon).
        r = V.analisis_valuasi(emiten_contoh()).relative
        self.assertIsNone(r.fair_value_per)   # mean tak tersedia
        self.assertIsNotNone(r.fair_value)    # tapi fallback mengisi
        self.assertEqual(r.metode_fair_value, "Justified P/B berbasis ROE (Gordon)")
        self.assertGreater(r.fair_value, 0)

    def test_tanpa_pasar_error(self):
        e = Emiten(profil=ProfilEmiten(kode="X", nama="X", sektor="s"),
                   laporan=[laporan(2024)], pasar=None)
        with self.assertRaises(ValueError):
            V.analisis_valuasi(e)


if __name__ == "__main__":
    unittest.main()
