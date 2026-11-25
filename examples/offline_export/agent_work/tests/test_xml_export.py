import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exporter import export_xml, read_rows


class XmlExportTest(unittest.TestCase):
    def test_exports_xml(self):
        rows = read_rows("data/input.csv")
        payload = export_xml(rows)
        self.assertIn("<name>alice</name>", payload)
        self.assertIn("<value>10</value>", payload)


if __name__ == "__main__":
    unittest.main()
