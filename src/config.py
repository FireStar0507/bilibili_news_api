from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    sessdata: str
    talker_id: int
    session_type: int = 1
    size: int = 20
    request_interval_sec: float = 1.5
    max_round: int = 10
    archive_dir: str = "."
    retry_times: int = 3
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )


def load_config(path: str | Path = "config.json") -> Config:
    data: dict = {}
    p = Path(path)
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))

    sessdata = os.environ.get("BILI_SESSDATA") or data.get("sessdata") or ""
    talker_raw = os.environ.get("BILI_TALKER_ID") or data.get("talker_id")
    if not sessdata:
        raise SystemExit("missing SESSDATA: set BILI_SESSDATA or config.json")
    if talker_raw in (None, ""):
        raise SystemExit("missing talker_id: set BILI_TALKER_ID or config.json")

    size = int(os.environ.get("BILI_SIZE") or data.get("size") or 20)
    size = min(max(size, 1), 200)
    interval = float(
        os.environ.get("BILI_REQUEST_INTERVAL")
        or data.get("request_interval_sec")
        or 1.5
    )
    interval = max(interval, 1.5)
    session_type = int(
        os.environ.get("BILI_SESSION_TYPE") or data.get("session_type") or 1
    )
    max_round = int(os.environ.get("BILI_MAX_ROUND") or data.get("max_round") or 10)
    archive_dir = str(
        os.environ.get("BILI_ARCHIVE_DIR") or data.get("archive_dir") or "."
    )
    retry_times = int(os.environ.get("BILI_RETRY_TIMES") or data.get("retry_times") or 3)
    user_agent = str(data.get("user_agent") or Config.user_agent)

    return Config(
        sessdata=str(sessdata),
        talker_id=int(talker_raw),
        session_type=session_type,
        size=size,
        request_interval_sec=interval,
        max_round=max_round,
        archive_dir=archive_dir,
        retry_times=retry_times,
        user_agent=user_agent,
    )
