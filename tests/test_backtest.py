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
        # Tren naik landai berosilasi ~24 hari (agar MA20 terisi & RSI moderat,
        # bukan overbought), lalu breakout +6% dgn volume tak naik, lalu hari
        # terakhir buka +4% (overnight menang & hit3). Memenuhi S2 termasuk
        # filter baru: close > MA20 dan RSI hari sebelum lonjakan < 70.
        closes = []
        p = 950.0
        for k in range(24):
            p = p * (1.012 if k % 2 == 0 else 0.994)
            closes.append(round(p, 2))
        breakout = round(closes[-1] * 1.06, 2)   # index 24: naik +6%
        closes += [breakout, breakout]            # index 25: hari terakhir
        opens = list(closes)                      # open harian lain tak dipakai S2
        opens[25] = round(breakout * 1.04, 2)     # open[i+1] = +4% overnight
        vols = [10_000_000.0] * len(closes)       # datar -> S2 lolos, S1 tidak
        return opens, closes, vols

    def test_s2_sinyal_dan_overnight(self):
        opens, closes, vols = self._series()
        bt = jalankan_backtest(opens, closes, vols, shares=1e10)
        # Index 24 (breakout) memenuhi S2; index 25 = hari terakhir (tak dihitung).
        self.assertEqual(bt["s2"]["sinyal"], 1)
        self.assertEqual(bt["s2"]["menang"], 1)
        self.assertEqual(bt["s2"]["hit3"], 1)      # overnight +4% >= 3%
        self.assertAlmostEqual(bt["s2"]["ret_total"], 0.04, places=3)
        # Gabungan: S1 & S2 bertentangan -> AND selalu 0; OR = union (di sini = S2).
        self.assertEqual(bt["s_and"]["sinyal"], 0)
        self.assertEqual(bt["s_or"]["sinyal"], bt["s1"]["sinyal"] + bt["s2"]["sinyal"])

    def test_volume_terlalu_besar_gagal(self):
        opens, closes, vols = self._series()
        vols[24] = 20_000_000.0  # volume >= 1.2x kemarin -> S2 gagal
        bt = jalankan_backtest(opens, closes, vols, shares=1e10)
        self.assertEqual(bt["s2"]["sinyal"], 0)

    def test_di_bawah_ma20_gagal(self):
        # Breakout tapi masih di bawah MA20 (baru bangkit dari jatuh) -> S2 tolak.
        closes = [2000.0] * 20 + [900.0, 954.0]   # anjlok lalu +6% (< MA20 ~1900)
        opens = list(closes)
        vols = [10_000_000.0] * len(closes)
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


class TestCircuitBreaker(unittest.TestCase):
    def test_sinyal_masuk_akal(self):
        from draftnest.pipeline import sinyal_masuk_akal
        # Normal: sedikit sinyal -> sahih
        self.assertTrue(sinyal_masuk_akal(2, 950))
        self.assertTrue(sinyal_masuk_akal(30, 950))
        # Rusak: ratusan sinyal -> ditolak
        self.assertFalse(sinyal_masuk_akal(350, 950))
        # Universe kosong -> ditolak
        self.assertFalse(sinyal_masuk_akal(0, 0))


if __name__ == "__main__":
    unittest.main()
