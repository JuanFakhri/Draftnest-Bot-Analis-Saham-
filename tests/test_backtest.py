import unittest

from draftnest.backtest import agregasi, jalankan_backtest, rsi, sma


class TestIndikator(unittest.TestCase):
    def test_sma(self):
        s = sma([1, 2, 3, 4, 5], 3)
        self.assertIsNone(s[0])
        self.assertIsNone(s[1])
        self.assertAlmostEqual(s[2], 2.0)
        self.assertAlmostEqual(s[4], 4.0)

    def test_rsi_naik_terus_100(self):
        closes = [float(x) for x in range(1, 40)]  # naik terus
        r = rsi(closes, 14)
        self.assertIsNone(r[13])
        self.assertAlmostEqual(r[20], 100.0)  # tak ada loss -> RSI 100


class TestBacktestS2(unittest.TestCase):
    def _series(self):
        # 8 hari flat di 1000 (vol 10jt), lalu hari ke-9 breakout +6% dgn volume
        # turun, hari ke-10 buka +4% (overnight menang & hit3).
        closes = [1000.0] * 8 + [1060.0, 1060.0]
        opens = [1000.0] * 8 + [1030.0, 1102.4]  # open[9] = 1060*1.04
        vols = [10_000_000.0] * 8 + [11_000_000.0, 10_000_000.0]
        return opens, closes, vols

    def test_s2_sinyal_dan_overnight(self):
        opens, closes, vols = self._series()
        bt = jalankan_backtest(opens, closes, vols, shares=1e10)
        # Hari index 8 (breakout) memenuhi S2; index 9 = hari terakhir (tak dihitung).
        self.assertEqual(bt["s2"]["sinyal"], 1)
        self.assertEqual(bt["s2"]["menang"], 1)
        self.assertEqual(bt["s2"]["hit3"], 1)      # overnight +4% >= 3%
        self.assertAlmostEqual(bt["s2"]["ret_total"], 0.04, places=4)
        # Gabungan: S1 & S2 bertentangan -> AND selalu 0; OR = union (di sini = S2).
        self.assertEqual(bt["s_and"]["sinyal"], 0)
        self.assertEqual(bt["s_or"]["sinyal"], bt["s1"]["sinyal"] + bt["s2"]["sinyal"])

    def test_volume_terlalu_besar_gagal(self):
        opens, closes, vols = self._series()
        vols[8] = 20_000_000.0  # volume >= 1.2x kemarin -> S2 gagal
        bt = jalankan_backtest(opens, closes, vols, shares=1e10)
        self.assertEqual(bt["s2"]["sinyal"], 0)


class TestAgregasi(unittest.TestCase):
    def test_agregasi_rate(self):
        per = [
            {"s1": {"sinyal": 10, "menang": 6, "hit3": 3, "ret_total": 0.2, "sinyal_terakhir": True},
             "s2": {"sinyal": 0, "menang": 0, "hit3": 0, "ret_total": 0.0, "sinyal_terakhir": False}},
            {"s1": {"sinyal": 10, "menang": 4, "hit3": 1, "ret_total": -0.1, "sinyal_terakhir": False},
             "s2": {"sinyal": 5, "menang": 3, "hit3": 2, "ret_total": 0.15, "sinyal_terakhir": True}},
        ]
        agg = agregasi(per)
        self.assertEqual(agg["s1"]["total_sinyal"], 20)
        self.assertAlmostEqual(agg["s1"]["win_rate"], 0.5)
        self.assertAlmostEqual(agg["s1"]["peluang_3persen"], 0.2)
        self.assertEqual(agg["s1"]["emiten_sinyal_terakhir"], 1)
        self.assertEqual(agg["s2"]["total_sinyal"], 5)
        self.assertEqual(agg["s2"]["emiten_sinyal_terakhir"], 1)


if __name__ == "__main__":
    unittest.main()
