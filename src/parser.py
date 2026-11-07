from __future__ import annotations

import json
import logging
import time

from src.image_store import ImageStore
from src.models import MessageRow, ParsedMessage, RawMessage
from src.storage import SqliteArchive

log = logging.getLogger("parser")


def _loads(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def parse_raw(msg: RawMessage, talker_id: int) -> ParsedMessage:
    obj = _loads(msg.content)
    content_text = None
    image_url = None
    image_ext = None
    if msg.msg_type == 1 and obj is not None:
        text = obj.get("content")
        if isinstance(text, str):
            content_text = text
    elif msg.msg_type == 2 and obj is not None:
        url = obj.get("url")
        if isinstance(url, str) and url:
            image_url = url
            image_type = obj.get("imageType")
            image_ext = str(image_type) if image_type else None
    return ParsedMessage(
        seqno=int(msg.seqno),
        talker_id=int(talker_id),
        sender_uid=int(msg.sender_uid),
        timestamp=int(msg.timestamp),
        msg_type=int(msg.msg_type),
        msg_status=int(msg.msg_status),
        content_text=content_text,
        raw_content=msg.content,
        image_url=image_url,
        image_ext=image_ext,
    )


class MessageParser:
    def __init__(self, db: SqliteArchive, images: ImageStore) -> None:
        self.db = db
        self.images = images

    def persist(self, msg: RawMessage, talker_id: int) -> bool:
        parsed = parse_raw(msg, talker_id)
        image_path = None
        if parsed.image_url:
            image_path = self.images.save(
                parsed.seqno, parsed.timestamp, parsed.image_url, parsed.image_ext
            )
        row = MessageRow(
            seqno=parsed.seqno,
            talker_id=parsed.talker_id,
            sender_uid=parsed.sender_uid,
            timestamp=parsed.timestamp,
            msg_type=parsed.msg_type,
            msg_status=parsed.msg_status,
            content_text=parsed.content_text,
            raw_content=parsed.raw_content,
            image_local_path=image_path,
            created_at=int(time.time()),
        )
        return self.db.insert_if_absent(row)
