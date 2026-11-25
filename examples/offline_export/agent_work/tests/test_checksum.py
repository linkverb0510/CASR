import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from checksum import checksum_rows
from exporter import read_rows


class ChecksumTest(unittest.TestCase):
    def test_checksum_is_stable(self):
        rows = read_rows("data/input.csv")
        self.assertEqual(len(checksum_rows(rows)), 64)
        self.assertEqual(checksum_rows(rows), checksum_rows(rows))


if __name__ == "__main__":
    unittest.main()
