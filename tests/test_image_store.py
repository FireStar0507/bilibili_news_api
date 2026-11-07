import unittest
from datetime import datetime, timezone

from src.image_store import decade_relpath, guess_ext


def _ts(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


class DecadePathTests(unittest.TestCase):
    def test_first_decade(self):
        self.assertEqual(decade_relpath(_ts(2025, 2, 1), 123, ".jpg"), "2025/02/01-10/123.jpg")

    def test_day_10(self):
        self.assertEqual(decade_relpath(_ts(2025, 2, 10), 1, ".png"), "2025/02/01-10/1.png")

    def test_day_11(self):
        self.assertEqual(decade_relpath(_ts(2025, 2, 11), 2, ".jpg"), "2025/02/11-20/2.jpg")

    def test_day_21_non_leap_feb(self):
        self.assertEqual(decade_relpath(_ts(2025, 2, 21), 3, ".jpg"), "2025/02/21-28/3.jpg")

    def test_dec_late(self):
        self.assertEqual(decade_relpath(_ts(2026, 12, 21), 456, ".jpg"), "2026/12/21-31/456.jpg")

    def test_guess_ext(self):
        self.assertEqual(guess_ext("https://x/a.jpg", None), ".jpg")
        self.assertEqual(guess_ext("https://x/a", "png"), ".png")
        self.assertEqual(guess_ext("https://x/a", None), ".jpg")


if __name__ == "__main__":
    unittest.main()
