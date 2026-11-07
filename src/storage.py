from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from src.models import MessageRow

SCHEMA = """
CREATE TABLE IF NOT EXISTS private_messages (
    seqno INTEGER PRIMARY KEY,
    talker_id INTEGER NOT NULL,
    sender_uid INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    msg_type INTEGER NOT NULL,
    msg_status INTEGER NOT NULL,
    content_text TEXT,
    raw_content TEXT,
    image_local_path TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_private_messages_talker_seqno
    ON private_messages(talker_id, seqno);
"""


class SqliteArchive:
    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.conn.close()

    def get_max_seqno(self, talker_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(seqno) FROM private_messages WHERE talker_id = ?",
            (talker_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    def exists(self, seqno: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM private_messages WHERE seqno = ? LIMIT 1",
            (seqno,),
        ).fetchone()
        return row is not None

    def insert_if_absent(self, row: MessageRow) -> bool:
        if self.exists(row.seqno):
            return False
        created_at = row.created_at or int(time.time())
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO private_messages (
                seqno, talker_id, sender_uid, timestamp, msg_type, msg_status,
                content_text, raw_content, image_local_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.seqno,
                row.talker_id,
                row.sender_uid,
                row.timestamp,
                row.msg_type,
                row.msg_status,
                row.content_text,
                row.raw_content,
                row.image_local_path,
                created_at,
            ),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_by_talker(
        self, talker_id: int, limit: int = 100, after_seqno: int = 0
    ) -> list[tuple]:
        return self.conn.execute(
            """
            SELECT seqno, talker_id, sender_uid, timestamp, msg_type, msg_status,
                   content_text, raw_content, image_local_path, created_at
            FROM private_messages
            WHERE talker_id = ? AND seqno > ?
            ORDER BY seqno ASC
            LIMIT ?
            """,
            (talker_id, after_seqno, limit),
        ).fetchall()

    def count(self, talker_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM private_messages WHERE talker_id = ?",
            (talker_id,),
        ).fetchone()
        return int(row[0]) if row else 0
