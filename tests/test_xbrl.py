import unittest

from draftnest.idx_scraper import IDXError, emiten_ke_dict, parse_xbrl
from draftnest.models import Emiten, ProfilEmiten
from tests.fixtures import laporan

XBRL = b"""<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:idx="http://x">
<idx:CurrentPeriodEndDate contextRef="c">2024-12-31</idx:CurrentPeriodEndDate>
<idx:Assets contextRef="CurrentYearInstant">130000</idx:Assets>
<idx:CurrentAssets contextRef="CurrentYearInstant">46000</idx:CurrentAssets>
<idx:Liabilities contextRef="CurrentYearInstant">59000</idx:Liabilities>
<idx:CurrentLiabilities contextRef="CurrentYearInstant">22000</idx:CurrentLiabilities>
<idx:Equity contextRef="CurrentYearInstant">71000</idx:Equity>
<idx:SalesAndRevenue contextRef="CurrentYearDuration">72000</idx:SalesAndRevenue>
<idx:GrossProfit contextRef="CurrentYearDuration">26000</idx:GrossProfit>
<idx:ProfitLossFromOperatingActivities contextRef="CurrentYearDuration">15500</idx:ProfitLossFromOperatingActivities>
<idx:ProfitLoss contextRef="CurrentYearDuration">9200</idx:ProfitLoss>
<idx:NetCashFlowsReceivedFromUsedInOperatingActivities contextRef="CurrentYearDuration">12500</idx:NetCashFlowsReceivedFromUsedInOperatingActivities>
<idx:NetCashFlowsReceivedFromUsedInInvestingActivities contextRef="CurrentYearDuration">-6000</idx:NetCashFlowsReceivedFromUsedInInvestingActivities>
<idx:NetCashFlowsReceivedFromUsedInFinancingActivities contextRef="CurrentYearDuration">-3500</idx:NetCashFlowsReceivedFromUsedInFinancingActivities>
</xbrl>"""


class TestXBRL(unittest.TestCase):
    def test_parse_lengkap(self):
        lap = parse_xbrl(XBRL)
        self.assertEqual(lap.tahun, 2024)
        self.assertEqual(lap.total_aset, 130000)
        self.assertEqual(lap.total_ekuitas, 71000)
        self.assertEqual(lap.pendapatan, 72000)
        self.assertEqual(lap.laba_bersih, 9200)
        self.assertEqual(lap.arus_kas_operasi, 12500)
        self.assertEqual(lap.arus_kas_investasi, -6000)

    def test_override_tahun(self):
        lap = parse_xbrl(XBRL, tahun=2099)
        self.assertEqual(lap.tahun, 2099)

    def test_konsep_kosong_error(self):
        kosong = b'<?xml version="1.0"?><xbrl xmlns="http://x"><foo>1</foo></xbrl>'
        with self.assertRaises(IDXError):
            parse_xbrl(kosong)

    def test_konsep_wajib_hilang_error(self):
        # Hanya total_aset -> field wajib lain hilang
        parsial = (
            b'<?xml version="1.0"?><xbrl xmlns:idx="http://x">'
            b'<idx:Assets contextRef="CurrentYearInstant">1</idx:Assets>'
            b'<idx:CurrentPeriodEndDate contextRef="c">2024-12-31</idx:CurrentPeriodEndDate>'
            b"</xbrl>"
        )
        with self.assertRaises(IDXError):
            parse_xbrl(parsial)

    def test_serialisasi_dict(self):
        e = Emiten(
            profil=ProfilEmiten(kode="ICBP", nama="ICBP", sektor="Consumer"),
            laporan=[laporan(2024)],
            pasar=None,
        )
        d = emiten_ke_dict(e)
        self.assertEqual(d["profil"]["kode"], "ICBP")
        self.assertEqual(len(d["laporan"]), 1)
        self.assertNotIn("pasar", d)


if __name__ == "__main__":
    unittest.main()
