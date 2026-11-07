from __future__ import annotations

import json
import os
from pathlib import Path


class ResumePointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("resume_point.json root must be an object")
        return data

    def get(self, talker_id: int) -> dict:
        data = self._load()
        rec = data.get(str(talker_id)) or {}
        return {
            "last_begin_seqno": rec.get("last_begin_seqno"),
            "has_finished": bool(rec.get("has_finished", False)),
        }

    def save(
        self,
        talker_id: int,
        last_begin_seqno: int | None,
        has_finished: bool,
    ) -> None:
        data = self._load()
        data[str(talker_id)] = {
            "last_begin_seqno": last_begin_seqno,
            "has_finished": bool(has_finished),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
