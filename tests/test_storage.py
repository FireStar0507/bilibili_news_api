import tempfile
import unittest
from pathlib import Path

from src.models import MessageRow
from src.storage import SqliteArchive


def _row(seqno, talker_id=1, timestamp=100, **kwargs):
    data = dict(
        seqno=seqno,
        talker_id=talker_id,
        sender_uid=2,
        timestamp=timestamp,
        msg_type=1,
        msg_status=0,
        content_text="t",
        raw_content="{}",
        image_local_path=None,
        created_at=1,
    )
    data.update(kwargs)
    return MessageRow(**data)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = SqliteArchive(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_insert_and_dedup(self):
        self.assertTrue(self.db.insert_if_absent(_row(10)))
        self.assertFalse(self.db.insert_if_absent(_row(10)))
        self.assertEqual(self.db.count(1), 1)

    def test_max_seqno(self):
        self.assertIsNone(self.db.get_max_seqno(1))
        self.db.insert_if_absent(_row(5))
        self.db.insert_if_absent(_row(9))
        self.assertEqual(self.db.get_max_seqno(1), 9)

    def test_order_by_seqno_not_timestamp(self):
        self.db.insert_if_absent(_row(2, timestamp=50))
        self.db.insert_if_absent(_row(1, timestamp=90))
        rows = self.db.list_by_talker(1)
        self.assertEqual([r[0] for r in rows], [1, 2])


if __name__ == "__main__":
    unittest.main()
