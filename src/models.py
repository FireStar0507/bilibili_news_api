from dataclasses import dataclass


@dataclass
class RawMessage:
    seqno: int
    sender_uid: int
    timestamp: int
    msg_type: int
    msg_status: int
    content: str


@dataclass
class FetchResult:
    messages: list[RawMessage]
    has_more: int
    min_seqno: int
    max_seqno: int


@dataclass
class ParsedMessage:
    seqno: int
    talker_id: int
    sender_uid: int
    timestamp: int
    msg_type: int
    msg_status: int
    content_text: str | None
    raw_content: str | None
    image_url: str | None
    image_ext: str | None


@dataclass
class MessageRow:
    seqno: int
    talker_id: int
    sender_uid: int
    timestamp: int
    msg_type: int
    msg_status: int
    content_text: str | None
    raw_content: str | None
    image_local_path: str | None
    created_at: int
