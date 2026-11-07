from __future__ import annotations

import calendar
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("image_store")

_TYPE_EXT = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "bmp": ".bmp",
}


def decade_relpath(timestamp: int, seqno: int, ext: str) -> str:
    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    last = calendar.monthrange(dt.year, dt.month)[1]
    if dt.day <= 10:
        span = "01-10"
    elif dt.day <= 20:
        span = "11-20"
    else:
        span = f"21-{last:02d}"
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{dt.year}/{dt.month:02d}/{span}/{seqno}{ext}"


def guess_ext(url: str, image_type: str | None) -> str:
    if image_type:
        mapped = _TYPE_EXT.get(image_type.lower().lstrip("."))
        if mapped:
            return mapped
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


class ImageStore:
    def __init__(self, archive_dir: str, user_agent: str, timeout: int = 30) -> None:
        self.root = Path(archive_dir)
        self.user_agent = user_agent
        self.timeout = timeout

    def save(
        self, seqno: int, timestamp: int, url: str, image_type: str | None
    ) -> str | None:
        ext = guess_ext(url, image_type)
        rel = decade_relpath(timestamp, seqno, ext)
        dest = self.root / rel
        if dest.is_file() and dest.stat().st_size > 0:
            return rel.replace("\\", "/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Referer": "https://message.bilibili.com/",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            log.warning("image download failed seqno=%s url=%s err=%s", seqno, url, exc)
            return None
        if not data:
            log.warning("empty image body seqno=%s url=%s", seqno, url)
            return None
        guessed = mimetypes.guess_extension((ctype or "").split(";")[0].strip())
        if guessed == ".jpeg":
            guessed = ".jpg"
        if guessed in {".jpg", ".png", ".gif", ".webp", ".bmp"} and guessed != ext:
            ext = guessed
            rel = decade_relpath(timestamp, seqno, ext)
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return rel.replace("\\", "/")
