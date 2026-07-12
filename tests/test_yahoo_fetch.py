import sys
import types
import unittest

try:
    import pandas  # noqa: F401
    _PANDAS = True
except ImportError:
    _PANDAS = False


def _fake_yfinance(info, income, balance, cash, history=None):
    """Bangun modul yfinance palsu dengan satu Ticker."""
    import pandas as pd

    mod = types.ModuleType("yfinance")

    class T:
        def __init__(self, _sym):
            pass

        info = None
        income_stmt = None
        balance_sheet = None
        cashflow = None

        def history(self, period="6y"):
            return history if history is not None else pd.DataFrame()

    T.info = info
    T.income_stmt = income
    T.balance_sheet = balance
    T.cashflow = cash
    mod.Ticker = T
    return mod


@unittest.skipUnless(_PANDAS, "pandas tak terpasang (hanya diperlukan pipeline data)")
class TestYahooFetch(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        from datetime import datetime

        self.pd = pd
        # 3 kolom tahun; 2021 sengaja "hantu" (semua nol di balance/income).
        self.cols = [pd.Timestamp(datetime(2024, 12, 31)),
                     pd.Timestamp(datetime(2023, 12, 31)),
                     pd.Timestamp(datetime(2021, 12, 31))]

    def _dfs(self):
        pd = self.pd
        c0, c1, c2 = self.cols
        income = pd.DataFrame({
            c0: {"Total Revenue": 72000, "Gross Profit": 26000, "Operating Income": 15500, "Net Income": 9200},
            c1: {"Total Revenue": 67000, "Gross Profit": 23500, "Operating Income": 14000, "Net Income": 8000},
            c2: {"Total Revenue": None, "Net Income": None},  # tahun hantu
        })
        balance = pd.DataFrame({
            c0: {"Total Assets": 130000, "Current Assets": 46000, "Total Liabilities Net Minority Interest": 59000, "Current Liabilities": 22000, "Stockholders Equity": 71000},
            c1: {"Total Assets": 122000, "Current Assets": 43000, "Total Liabilities Net Minority Interest": 61000, "Current Liabilities": 21000, "Stockholders Equity": 61000},
            c2: {"Total Assets": None},  # tahun hantu
        })
        cash = pd.DataFrame({
            c0: {"Operating Cash Flow": 12500, "Investing Cash Flow": -6000, "Financing Cash Flow": -3500},
            c1: {"Operating Cash Flow": 11000, "Investing Cash Flow": -5500, "Financing Cash Flow": -3000},
            c2: {},
        })
        return income, balance, cash

    def _patch(self, info):
        income, balance, cash = self._dfs()
        sys.modules["yfinance"] = _fake_yfinance(info, income, balance, cash)

    def tearDown(self):
        sys.modules.pop("yfinance", None)

    def test_lewati_tahun_hantu(self):
        self._patch({"longName": "PT X", "sector": "S", "currentPrice": 100, "sharesOutstanding": 1000})
        from draftnest.yahoo_fetch import fetch_emiten
        e = fetch_emiten("X")
        tahun = [l.tahun for l in e.laporan_urut()]
        self.assertNotIn(2021, tahun)      # tahun hantu dibuang
        self.assertEqual(tahun, [2023, 2024])

    def test_catatan_mata_uang(self):
        self._patch({"longName": "PT X", "sector": "S", "currentPrice": 100,
                     "sharesOutstanding": 1000, "financialCurrency": "USD", "currency": "IDR"})
        from draftnest.yahoo_fetch import fetch_emiten
        e = fetch_emiten("X")
        self.assertIn("USD", e.profil.berita_terkini)
        self.assertIn("IDR", e.profil.berita_terkini)

    def test_tanpa_mismatch_tanpa_catatan(self):
        self._patch({"longName": "PT X", "sector": "S", "currentPrice": 100,
                     "sharesOutstanding": 1000, "financialCurrency": "IDR", "currency": "IDR"})
        from draftnest.yahoo_fetch import fetch_emiten
        e = fetch_emiten("X")
        self.assertEqual(e.profil.berita_terkini, "")


if __name__ == "__main__":
    unittest.main()
