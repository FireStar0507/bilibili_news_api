import json
import unittest

from src.models import RawMessage
from src.parser import parse_raw


def _msg(**kwargs):
    base = dict(
        seqno=1,
        sender_uid=2,
        timestamp=3,
        msg_type=1,
        msg_status=0,
        content='{"content":"hi"}',
    )
    base.update(kwargs)
    return RawMessage(**base)


class ParserTests(unittest.TestCase):
    def test_text(self):
        p = parse_raw(_msg(), talker_id=9)
        self.assertEqual(p.content_text, "hi")
        self.assertIsNone(p.image_url)
        self.assertEqual(p.raw_content, '{"content":"hi"}')

    def test_image(self):
        content = json.dumps({"url": "https://x/a.png", "imageType": "png"})
        p = parse_raw(_msg(msg_type=2, content=content), talker_id=9)
        self.assertIsNone(p.content_text)
        self.assertEqual(p.image_url, "https://x/a.png")
        self.assertEqual(p.image_ext, "png")

    def test_other_keeps_raw(self):
        p = parse_raw(_msg(msg_type=10, content='{"title":"n"}'), talker_id=9)
        self.assertIsNone(p.content_text)
        self.assertIsNone(p.image_url)
        self.assertEqual(p.raw_content, '{"title":"n"}')

    def test_bad_json(self):
        p = parse_raw(_msg(content="not-json"), talker_id=9)
        self.assertIsNone(p.content_text)
        self.assertEqual(p.raw_content, "not-json")

    def test_withdrawn_still_parsed(self):
        p = parse_raw(_msg(msg_status=1), talker_id=9)
        self.assertEqual(p.content_text, "hi")
        self.assertEqual(p.msg_status, 1)


if __name__ == "__main__":
    unittest.main()
