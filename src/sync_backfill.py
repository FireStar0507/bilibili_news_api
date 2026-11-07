from __future__ import annotations

import logging

from src.api_client import SessionMsgClient
from src.parser import MessageParser
from src.resume import ResumePointStore
from src.storage import SqliteArchive

log = logging.getLogger("sync_backfill")


def backfill_history(
    db: SqliteArchive,
    client: SessionMsgClient,
    parser: MessageParser,
    resume: ResumePointStore,
    talker_id: int,
    session_type: int,
    size: int,
    max_round: int,
) -> dict:
    point = resume.get(talker_id)
    if point["has_finished"]:
        log.info("backfill skipped, has_finished=true talker_id=%s", talker_id)
        return {"status": "finished", "inserted": 0, "rounds": 0}

    begin = point["last_begin_seqno"]
    inserted = 0
    skipped = 0
    rounds = 0
    finished = False
    while rounds < max_round:
        result = client.fetch(talker_id, session_type, size, begin_seqno=begin)
        for msg in result.messages:
            if parser.persist(msg, talker_id):
                inserted += 1
            else:
                skipped += 1
        rounds += 1
        begin = result.min_seqno if result.min_seqno else begin
        finished = int(result.has_more) == 0
        resume.save(talker_id, last_begin_seqno=begin, has_finished=finished)
        log.info(
            "backfill round=%s min_seqno=%s has_more=%s inserted=%s",
            rounds,
            begin,
            result.has_more,
            inserted,
        )
        if finished:
            break
        if not result.messages:
            break
    return {
        "status": "finished" if finished else "paused",
        "inserted": inserted,
        "skipped": skipped,
        "rounds": rounds,
        "last_begin_seqno": begin,
    }
