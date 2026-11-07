from __future__ import annotations

import logging

from src.api_client import SessionMsgClient
from src.parser import MessageParser
from src.storage import SqliteArchive

log = logging.getLogger("sync_incremental")


def incremental_sync(
    db: SqliteArchive,
    client: SessionMsgClient,
    parser: MessageParser,
    talker_id: int,
    session_type: int,
    size: int,
) -> dict:
    anchor = db.get_max_seqno(talker_id) or 0
    inserted = 0
    skipped = 0
    rounds = 0
    begin = None
    while True:
        result = client.fetch(talker_id, session_type, size, begin_seqno=begin)
        newer = [m for m in result.messages if m.seqno > anchor]
        if not newer:
            break
        for msg in sorted(newer, key=lambda m: m.seqno):
            if parser.persist(msg, talker_id):
                inserted += 1
            else:
                skipped += 1
        rounds += 1
        log.info(
            "incremental round=%s inserted=%s anchor=%s batch_newer=%s min=%s",
            rounds,
            inserted,
            anchor,
            len(newer),
            result.min_seqno,
        )
        if anchor == 0:
            break
        if result.min_seqno <= anchor:
            break
        begin = result.min_seqno
    return {
        "inserted": inserted,
        "skipped": skipped,
        "rounds": rounds,
        "local_max": db.get_max_seqno(talker_id) or 0,
    }
