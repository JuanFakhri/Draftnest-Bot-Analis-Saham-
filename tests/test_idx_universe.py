import tempfile
import unittest
from pathlib import Path

from draftnest import idx_universe as U

CSV = """No,Kode,Nama Perusahaan,Tanggal Pencatatan,Saham,Papan Pencatatan
1,AALI,Astra Agro Lestari Tbk.,09 Des 1997,1.924.688.333,Utama
2,ABBA,Mahaka Media Tbk.,03 Apr 2002,3.935.892.857,Pemantauan Khusus
3,BEI: ACES,Aspirasi Hidup Indonesia Tbk.,06 Nov 2007,17.120.389.700,Utama
"""


class TestIdxUniverse(unittest.TestCase):
    def test_parse_csv(self):
        kode = U.parse_csv_kode(CSV)
        self.assertEqual(kode, ["AALI", "ABBA", "ACES"])  # header dilewati, "BEI: ACES" tertangani

    def test_parse_file(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("# komentar\nBBCA\nbbri  # inline\n\nTLKM\nXX\nTOOLONG\n")
        f.close()
        self.assertEqual(U._dari_file(Path(f.name)), ["BBCA", "BBRI", "TLKM"])

    def test_union_dan_fallback(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("TLKM\nBBCA\n")
        f.close()
        asli_sumber, asli_csv = U.SUMBER_CSV, U._dari_csv
        # 1) Semua CSV sukses -> union unik & terurut, fallback tak dipakai.
        U.SUMBER_CSV = ["a", "b"]
        U._dari_csv = lambda url: ["BBRI", "AALI"] if url == "a" else ["AALI", "ASII"]
        try:
            self.assertEqual(U.daftar_emiten(fallback_file=Path(f.name)), ["AALI", "ASII", "BBRI"])
            # 2) Semua CSV gagal -> pakai fallback file.
            U._dari_csv = lambda url: (_ for _ in ()).throw(RuntimeError("blocked"))
            self.assertEqual(U.daftar_emiten(fallback_file=Path(f.name)), ["BBCA", "TLKM"])
        finally:
            U.SUMBER_CSV, U._dari_csv = asli_sumber, asli_csv


if __name__ == "__main__":
    unittest.main()
