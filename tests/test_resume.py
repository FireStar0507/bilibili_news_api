import json
import tempfile
import unittest
from pathlib import Path

from src.resume import ResumePointStore


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "resume_point.json"
        self.store = ResumePointStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_and_save(self):
        rec = self.store.get(123)
        self.assertIsNone(rec["last_begin_seqno"])
        self.assertFalse(rec["has_finished"])
        self.store.save(123, last_begin_seqno=99, has_finished=False)
        rec = self.store.get(123)
        self.assertEqual(rec["last_begin_seqno"], 99)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("123", data)
        self.assertIsInstance(list(data.keys())[0], str)

    def test_finished(self):
        self.store.save(1, last_begin_seqno=1, has_finished=True)
        self.assertTrue(self.store.get(1)["has_finished"])


if __name__ == "__main__":
    unittest.main()
