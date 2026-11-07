from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.api_client import AuthExpiredError, RateLimitedError, ApiError, SessionMsgClient
from src.config import load_config
from src.image_store import ImageStore
from src.parser import MessageParser
from src.resume import ResumePointStore
from src.storage import SqliteArchive
from src.sync_backfill import backfill_history
from src.sync_incremental import incremental_sync


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def _build(cfg):
    root = Path(cfg.archive_dir)
    db = SqliteArchive(root / "bilibili_msg_archive.db")
    images = ImageStore(str(root), cfg.user_agent)
    parser = MessageParser(db, images)
    client = SessionMsgClient(
        sessdata=cfg.sessdata,
        user_agent=cfg.user_agent,
        request_interval_sec=cfg.request_interval_sec,
        retry_times=cfg.retry_times,
    )
    resume = ResumePointStore(root / "resume_point.json")
    return db, client, parser, resume


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Bilibili private message archive")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sync", help="incremental catch-up")
    bf = sub.add_parser("backfill", help="history backfill")
    bf.add_argument("--max-round", type=int, default=None)
    sub.add_parser("status", help="print local archive stats")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    db, client, msg_parser, resume = _build(cfg)
    try:
        if args.cmd == "sync":
            result = incremental_sync(
                db, client, msg_parser, cfg.talker_id, cfg.session_type, cfg.size
            )
            print(result)
            return 0
        if args.cmd == "backfill":
            max_round = args.max_round if args.max_round is not None else cfg.max_round
            result = backfill_history(
                db,
                client,
                msg_parser,
                resume,
                cfg.talker_id,
                cfg.session_type,
                cfg.size,
                max_round,
            )
            print(result)
            return 0
        if args.cmd == "status":
            local_max = db.get_max_seqno(cfg.talker_id)
            point = resume.get(cfg.talker_id)
            print(
                {
                    "talker_id": cfg.talker_id,
                    "count": db.count(cfg.talker_id),
                    "local_max_seqno": local_max,
                    "resume": point,
                }
            )
            return 0
    except AuthExpiredError as exc:
        logging.error("%s; update BILI_SESSDATA", exc)
        return 2
    except RateLimitedError as exc:
        logging.error("%s; increase interval and retry", exc)
        return 3
    except ApiError as exc:
        logging.error("%s", exc)
        return 4
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
