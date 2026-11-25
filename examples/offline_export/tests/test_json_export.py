import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exporter import export_json, read_rows


class JsonExportTest(unittest.TestCase):
    def test_exports_json(self):
        rows = read_rows("data/input.csv")
        payload = export_json(rows)
        self.assertIn('"name": "alice"', payload)
        self.assertNotIn("<row>", payload)


if __name__ == "__main__":
    unittest.main()
