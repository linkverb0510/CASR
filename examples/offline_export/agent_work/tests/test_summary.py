import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exporter import read_rows
from summary import summarize


class SummaryTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(summarize(read_rows("data/input.csv")), {"count": 3, "total": 60})


if __name__ == "__main__":
    unittest.main()
