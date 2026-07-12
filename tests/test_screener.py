import unittest

from draftnest.models import DataPasar, Emiten, ProfilEmiten
from draftnest.screener import (
    KriteriaScreener,
    lolos,
    naik_tiap_tahun,
    ringkas_emiten,
    saring,
)
from tests.fixtures import laporan


def _emiten_tumbuh(dividen_yield=None, beruntun=0):
    # Pendapatan & laba naik tiap tahun, ROE sehat, leverage rendah.
    return Emiten(
        profil=ProfilEmiten(kode="GROW", nama="Grow Tbk", sektor="Consumer"),
        laporan=[
            laporan(2022, pendapatan=100000, laba_bersih=12000, total_ekuitas=60000,
                    total_liabilitas=30000, aset_lancar=40000, liabilitas_lancar=15000),
            laporan(2023, pendapatan=120000, laba_bersih=15000, total_ekuitas=68000,
                    total_liabilitas=32000, aset_lancar=45000, liabilitas_lancar=15000),
            laporan(2024, pendapatan=145000, laba_bersih=19000, total_ekuitas=78000,
                    total_liabilitas=34000, aset_lancar=52000, liabilitas_lancar=16000),
        ],
        pasar=DataPasar(harga_saham=8000, saham_beredar=5000, mean_per_3y=15.0,
                        dividend_yield=dividen_yield, dividen_beruntun=beruntun),
    )


class TestNaikTiapTahun(unittest.TestCase):
    def test_naik(self):
        self.assertTrue(naik_tiap_tahun([10, 12, 15]))

    def test_tidak_naik(self):
        self.assertFalse(naik_tiap_tahun([10, 9, 15]))

    def test_abaikan_nol_di_depan(self):
        # Tahun phantom (0) di depan diabaikan; sisanya naik.
        self.assertTrue(naik_tiap_tahun([0, 10, 12, 15]))

    def test_kurang_titik(self):
        self.assertIsNone(naik_tiap_tahun([10, 12]))  # < 3 titik


class TestRingkasEmiten(unittest.TestCase):
    def test_metrik_pertumbuhan_dan_skor(self):
        r = ringkas_emiten(_emiten_tumbuh())
        self.assertEqual(r["kode"], "GROW")
        self.assertTrue(r["naik_pendapatan"])
        self.assertTrue(r["naik_laba"])
        self.assertIsNotNone(r["roe"])
        self.assertIsNotNone(r["skor_akhir"])
        self.assertTrue(r["prospek_bagus"])


class TestFilter(unittest.TestCase):
    def test_lolos_pertumbuhan_prospek_tanpa_dividen(self):
        r = ringkas_emiten(_emiten_tumbuh())
        # Tanpa data dividen, kriteria dividen default (yield 7%) menolak.
        self.assertFalse(lolos(r, KriteriaScreener()))
        # Abaikan dividen -> lolos (pertumbuhan + prospek terpenuhi).
        k = KriteriaScreener(div_yield_min=None, div_yield_maks=None, div_beruntun_min=0)
        self.assertTrue(lolos(r, k))

    def test_dividen_dalam_rentang(self):
        r = ringkas_emiten(_emiten_tumbuh(dividen_yield=0.09, beruntun=5))
        self.assertTrue(lolos(r, KriteriaScreener()))          # 9% dalam 7-15%
        r_rendah = ringkas_emiten(_emiten_tumbuh(dividen_yield=0.04, beruntun=5))
        self.assertFalse(lolos(r_rendah, KriteriaScreener()))  # 4% < 7%

    def test_saring_urut_skor(self):
        data = [ringkas_emiten(_emiten_tumbuh(dividen_yield=0.09, beruntun=4))]
        hasil = saring(data, KriteriaScreener())
        self.assertEqual(len(hasil), 1)


if __name__ == "__main__":
    unittest.main()
