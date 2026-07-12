import tempfile
import unittest
from pathlib import Path

from draftnest import idx_universe as U


class TestIdxUniverse(unittest.TestCase):
    def test_parse_file(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("# komentar\nBBCA\nbbri  # inline\n\nTLKM\nXX\nTOOLONG\n")
        f.close()
        kode = U._dari_file(Path(f.name))
        self.assertEqual(kode, ["BBCA", "BBRI", "TLKM"])  # XX & TOOLONG ditolak (harus 4 huruf)

    def test_fallback_saat_idx_gagal(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        f.write("TLKM\nBBCA\nBBCA\nASII\n")
        f.close()
        # Paksa sumber IDX gagal -> harus pakai fallback file, unik & terurut.
        asli = U._dari_idx
        U._dari_idx = lambda: (_ for _ in ()).throw(RuntimeError("blocked"))
        try:
            kode = U.daftar_emiten(fallback_file=Path(f.name))
        finally:
            U._dari_idx = asli
        self.assertEqual(kode, ["ASII", "BBCA", "TLKM"])


if __name__ == "__main__":
    unittest.main()
