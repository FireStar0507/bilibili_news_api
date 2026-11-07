import tempfile
import unittest
from pathlib import Path

from src.models import FetchResult, RawMessage
from src.parser import MessageParser
from src.resume import ResumePointStore
from src.storage import SqliteArchive
from src.sync_backfill import backfill_history
from src.sync_incremental import incremental_sync


class FakeImages:
    def save(self, *args, **kwargs):
        return None


class FakeClient:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []

    def fetch(self, talker_id, session_type, size, begin_seqno=None):
        self.calls.append(begin_seqno)
        return self.batches.pop(0)


def _m(seqno):
    return RawMessage(seqno, 2, 100, 1, 0, '{"content":"x"}')


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = SqliteArchive(root / "t.db")
        self.resume = ResumePointStore(root / "resume_point.json")
        self.parser = MessageParser(self.db, FakeImages())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_respects_max_round_and_saves_point(self):
        client = FakeClient(
            [
                FetchResult([_m(30), _m(20)], 1, 20, 30),
                FetchResult([_m(19), _m(10)], 1, 10, 19),
            ]
        )
        result = backfill_history(
            self.db, client, self.parser, self.resume, 1, 1, 20, max_round=1
        )
        self.assertEqual(result["rounds"], 1)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.resume.get(1)["last_begin_seqno"], 20)
        self.assertFalse(self.resume.get(1)["has_finished"])
        self.assertEqual(client.calls, [None])

    def test_marks_finished(self):
        client = FakeClient([FetchResult([_m(5)], 0, 5, 5)])
        result = backfill_history(
            self.db, client, self.parser, self.resume, 1, 1, 20, max_round=5
        )
        self.assertEqual(result["status"], "finished")
        self.assertTrue(self.resume.get(1)["has_finished"])

    def test_skips_when_finished(self):
        self.resume.save(1, 1, True)
        client = FakeClient([FetchResult([_m(5)], 0, 5, 5)])
        result = backfill_history(
            self.db, client, self.parser, self.resume, 1, 1, 20, max_round=5
        )
        self.assertEqual(result["rounds"], 0)
        self.assertEqual(client.calls, [])

    def test_incremental_does_not_touch_resume(self):
        client = FakeClient([FetchResult([_m(8)], 0, 8, 8)])
        incremental_sync(self.db, client, self.parser, 1, 1, 20)
        self.assertFalse(Path(self.tmp.name, "resume_point.json").exists())


if __name__ == "__main__":
    unittest.main()
