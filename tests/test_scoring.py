import unittest

from draftnest import forecast as F
from draftnest import ratios as R
from draftnest import valuation as V
from draftnest.scoring import (
    analisis_deterministik,
    skor_kuantitatif,
    skor_valuasi,
)
from tests.fixtures import emiten_contoh, laporan
from draftnest.models import DataPasar, Emiten, ProfilEmiten


class TestSkorKuantitatif(unittest.TestCase):
    def test_bentuk_output_mirip_llm(self):
        kuant = R.analisis_kuantitatif(emiten_contoh())
        hasil = skor_kuantitatif(kuant)
        for field in ("profitabilitas", "solvabilitas", "likuiditas", "pertumbuhan"):
            self.assertIn(field, hasil)
            self.assertIn("skor", hasil[field])
            self.assertIn("justifikasi", hasil[field])
            self.assertTrue(1 <= hasil[field]["skor"] <= 10)
        self.assertIn("ringkasan", hasil)

    def test_profitabilitas_tinggi_skor_tinggi(self):
        # ROE tinggi -> laba besar relatif ekuitas kecil.
        em = Emiten(
            profil=ProfilEmiten(kode="XX", nama="X", sektor="S"),
            laporan=[
                laporan(2023, laba_bersih=25000, total_ekuitas=100000),
                laporan(2024, laba_bersih=30000, total_ekuitas=120000),
            ],
        )
        kuant = R.analisis_kuantitatif(em)
        hasil = skor_kuantitatif(kuant)
        # ROE 30000/120000 = 25% -> skor profitabilitas 10
        self.assertEqual(hasil["profitabilitas"]["skor"], 10)

    def test_der_tinggi_solvabilitas_rendah(self):
        em = Emiten(
            profil=ProfilEmiten(kode="XX", nama="X", sektor="S"),
            laporan=[
                laporan(2023, total_liabilitas=250000, total_ekuitas=50000),
                laporan(2024, total_liabilitas=260000, total_ekuitas=50000),
            ],
        )
        kuant = R.analisis_kuantitatif(em)
        hasil = skor_kuantitatif(kuant)
        # DER 260000/50000 = 5.2 -> skor solvabilitas terendah
        self.assertEqual(hasil["solvabilitas"]["skor"], 1)

    def test_pertumbuhan_butuh_dua_tahun(self):
        em = Emiten(
            profil=ProfilEmiten(kode="XX", nama="X", sektor="S"),
            laporan=[laporan(2024)],
        )
        kuant = R.analisis_kuantitatif(em)
        hasil = skor_kuantitatif(kuant)
        self.assertNotIn("pertumbuhan", hasil)


class TestSkorValuasi(unittest.TestCase):
    def test_bentuk_output_mirip_llm(self):
        em = emiten_contoh()
        valu = V.analisis_valuasi(em)
        proyeksi = F.proyeksi_tahun_depan(em)
        hasil = skor_valuasi(valu, proyeksi)
        self.assertIn("absolute_valuation", hasil)
        self.assertIn("status", hasil)
        self.assertIn(hasil["status"], ("undervalued", "fairvalued", "overvalued"))
        self.assertIn("kesimpulan_valuasi", hasil)

    def test_undervalued_saat_harga_di_bawah_fair_value(self):
        em = emiten_contoh()
        em.pasar.mean_per_3y = 20.0
        em.pasar.mean_pbv_3y = 4.0
        em.pasar.harga_saham = 5000  # jauh di bawah fair value
        valu = V.analisis_valuasi(em)
        hasil = skor_valuasi(valu)
        self.assertEqual(hasil["status"], "undervalued")
        self.assertGreaterEqual(hasil["relative_valuation"]["skor"], 8)


class TestAnalisisDeterministik(unittest.TestCase):
    def test_mengembalikan_kuant_dan_valu(self):
        em = emiten_contoh()
        kuant = R.analisis_kuantitatif(em)
        valu = V.analisis_valuasi(em)
        proyeksi = F.proyeksi_tahun_depan(em)
        kuant_skor, valu_skor = analisis_deterministik(em, kuant, valu, proyeksi)
        self.assertIn("profitabilitas", kuant_skor)
        self.assertIsNotNone(valu_skor)
        self.assertIn("status", valu_skor)

    def test_valu_none_tanpa_data_pasar(self):
        em = Emiten(
            profil=ProfilEmiten(kode="XX", nama="X", sektor="S"),
            laporan=[laporan(2023), laporan(2024)],
        )
        kuant = R.analisis_kuantitatif(em)
        kuant_skor, valu_skor = analisis_deterministik(em, kuant, None, None)
        self.assertIn("profitabilitas", kuant_skor)
        self.assertIsNone(valu_skor)


if __name__ == "__main__":
    unittest.main()
