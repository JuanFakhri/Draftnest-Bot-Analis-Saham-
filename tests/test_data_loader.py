import json
import tempfile
import unittest
from pathlib import Path

from draftnest.data_loader import muat_emiten


def _tulis(data):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.close()
    return f.name


class TestDataLoader(unittest.TestCase):
    def test_muat_contoh_repo(self):
        e = muat_emiten(Path(__file__).resolve().parent.parent / "data" / "ICBP.json")
        self.assertEqual(e.profil.kode, "ICBP")
        self.assertGreaterEqual(len(e.laporan), 2)
        self.assertIsNotNone(e.pasar)

    def test_profil_wajib(self):
        path = _tulis({"laporan": [{"tahun": 2024}]})
        with self.assertRaises(ValueError):
            muat_emiten(path)

    def test_laporan_wajib(self):
        path = _tulis({"profil": {"kode": "X", "nama": "X"}})
        with self.assertRaises(ValueError):
            muat_emiten(path)


if __name__ == "__main__":
    unittest.main()
