from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.models import FetchResult, RawMessage

log = logging.getLogger("api_client")

FETCH_URL = "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs"


class AuthExpiredError(RuntimeError):
    pass


class RateLimitedError(RuntimeError):
    pass


class ApiError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"api code={code} message={message}")
        self.code = code
        self.message = message


class SessionMsgClient:
    def __init__(
        self,
        sessdata: str,
        user_agent: str,
        request_interval_sec: float = 1.5,
        retry_times: int = 3,
        timeout: int = 30,
    ) -> None:
        self.sessdata = sessdata
        self.user_agent = user_agent
        self.request_interval_sec = max(float(request_interval_sec), 1.5)
        self.retry_times = retry_times
        self.timeout = timeout
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.request_interval_sec - (now - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

    def fetch(
        self,
        talker_id: int,
        session_type: int,
        size: int,
        begin_seqno: int | None = None,
    ) -> FetchResult:
        params = {
            "talker_id": talker_id,
            "session_type": session_type,
            "size": size,
            "build": 0,
            "mobi_app": "web",
        }
        if begin_seqno is not None:
            params["begin_seqno"] = begin_seqno
        url = f"{FETCH_URL}?{urlencode(params)}"
        last_err: Exception | None = None
        attempts = max(self.retry_times, 1)
        for i in range(attempts):
            self._throttle()
            req = Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Cookie": f"SESSDATA={self.sessdata}",
                    "Referer": "https://message.bilibili.com/",
                },
            )
            try:
                self._last_request_at = time.monotonic()
                with urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                return self._parse_body(body)
            except HTTPError as exc:
                if exc.code == 412:
                    raise RateLimitedError("http 412 rate limited") from exc
                last_err = exc
                log.warning("http error attempt=%s code=%s", i + 1, exc.code)
            except (URLError, TimeoutError, OSError) as exc:
                last_err = exc
                log.warning("network error attempt=%s err=%s", i + 1, exc)
            if i + 1 < attempts:
                time.sleep(min(2 ** i, 8))
        raise ApiError(-1, f"network failed: {last_err}")

    def _parse_body(self, body: bytes) -> FetchResult:
        payload = json.loads(body.decode("utf-8"))
        code = int(payload.get("code", -1))
        if code == -101:
            raise AuthExpiredError("SESSDATA expired")
        if code != 0:
            msg = str(payload.get("message") or payload.get("msg") or "")
            raise ApiError(code, msg)
        data = payload.get("data") or {}
        raw_list = data.get("messages") or []
        messages: list[RawMessage] = []
        for item in raw_list:
            messages.append(
                RawMessage(
                    seqno=int(item["msg_seqno"]),
                    sender_uid=int(item.get("sender_uid") or 0),
                    timestamp=int(item.get("timestamp") or 0),
                    msg_type=int(item.get("msg_type") or 0),
                    msg_status=int(item.get("msg_status") or 0),
                    content=item.get("content") or "",
                )
            )
        has_more = int(data.get("has_more") or 0)
        min_seqno = int(data.get("min_seqno") or 0)
        max_seqno = int(data.get("max_seqno") or 0)
        if messages and min_seqno == 0:
            min_seqno = min(m.seqno for m in messages)
        if messages and max_seqno == 0:
            max_seqno = max(m.seqno for m in messages)
        return FetchResult(
            messages=messages,
            has_more=has_more,
            min_seqno=min_seqno,
            max_seqno=max_seqno,
        )
