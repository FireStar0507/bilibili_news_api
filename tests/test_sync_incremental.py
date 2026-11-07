import tempfile
import unittest
from pathlib import Path

from src.models import FetchResult, RawMessage
from src.parser import MessageParser
from src.storage import SqliteArchive
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
        if not self.batches:
            return FetchResult([], 0, 0, 0)
        return self.batches.pop(0)


def _m(seqno):
    return RawMessage(seqno, 2, 100, 1, 0, '{"content":"x"}')


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = SqliteArchive(Path(self.tmp.name) / "t.db")
        self.parser = MessageParser(self.db, FakeImages())

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_empty_db_takes_latest_batch_only(self):
        client = FakeClient(
            [
                FetchResult([_m(30), _m(20)], 1, 20, 30),
                FetchResult([_m(19), _m(10)], 1, 10, 19),
            ]
        )
        result = incremental_sync(self.db, client, self.parser, 1, 1, 20)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(self.db.get_max_seqno(1), 30)
        self.assertEqual(client.calls, [None])

    def test_catch_up_walks_back_until_overlap(self):
        self.parser.persist(_m(10), 1)
        client = FakeClient(
            [
                FetchResult([_m(40), _m(30)], 1, 30, 40),
                FetchResult([_m(29), _m(11)], 1, 11, 29),
                FetchResult([_m(10), _m(9)], 1, 9, 10),
            ]
        )
        result = incremental_sync(self.db, client, self.parser, 1, 1, 20)
        self.assertEqual(result["inserted"], 4)
        self.assertEqual(self.db.count(1), 5)
        self.assertEqual(client.calls, [None, 30, 11])

    def test_skips_old_only_batch(self):
        self.parser.persist(_m(50), 1)
        client = FakeClient([FetchResult([_m(50), _m(40)], 1, 40, 50)])
        result = incremental_sync(self.db, client, self.parser, 1, 1, 20)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
