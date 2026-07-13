import unittest

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False


@unittest.skipUnless(_PANDAS, "butuh pandas")
class TestBSJPStats(unittest.TestCase):
    def _hist(self, closes, opens, vol=1_000_000):
        idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
        return pd.DataFrame(
            {"Open": opens, "Close": closes, "Volume": [vol] * len(closes)}, index=idx
        )

    def test_gap_konsisten_4persen(self):
        from draftnest.yahoo_fetch import _bsjp_stats
        n = 40
        closes = [100.0] * n
        opens = [100.0] + [104.0] * (n - 1)  # tiap pagi buka +4% dari close kemarin
        h = _bsjp_stats(self._hist(closes, opens), target=0.03)
        self.assertIsNotNone(h)
        self.assertEqual(h.sampel_hari, n - 1)
        self.assertAlmostEqual(h.peluang_naik_target, 1.0)   # selalu >= 3%
        self.assertAlmostEqual(h.win_rate, 1.0)
        self.assertAlmostEqual(h.rata_gap, 0.04, places=6)
        self.assertAlmostEqual(h.volume_rata, 1_000_000, places=0)

    def test_sampel_kurang_none(self):
        from draftnest.yahoo_fetch import _bsjp_stats
        h = _bsjp_stats(self._hist([100.0] * 10, [100.0] * 10))
        self.assertIsNone(h)   # < 30 gap

    def test_setengah_naik(self):
        from draftnest.yahoo_fetch import _bsjp_stats
        # Selang-seling: +5% lalu -1% -> peluang 3% ~ 0.5, win_rate ~ 0.5
        closes = [100.0] * 41
        opens = [100.0]
        for i in range(1, 41):
            opens.append(105.0 if i % 2 == 1 else 99.0)
        h = _bsjp_stats(self._hist(closes, opens), target=0.03)
        self.assertIsNotNone(h)
        self.assertAlmostEqual(h.peluang_naik_target, 0.5, places=1)
        self.assertAlmostEqual(h.win_rate, 0.5, places=1)


if __name__ == "__main__":
    unittest.main()
