#!/usr/bin/env python3
"""上传服务契约单测（不调 Gateway、不识图）。"""
from __future__ import annotations

import http.client
import io
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from server import (
    GATEWAY_UNREACHABLE,
    HttpError,
    IngestApp,
    build_agent_message,
    extract_agent_text,
    make_handler,
    parse_multipart,
    session_id_for,
)


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

# 眼镜 MicSession 出的是 MPEG_4 + AAC，只需要头部可辨认，服务端不解码。
M4A_STUB = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 32


def _multipart(fields: dict[str, str], files: dict[str, tuple[str, str, bytes]] | None = None) -> tuple[str, bytes]:
    boundary = "----testboundary"
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(value.encode("utf-8"))
        buf.write(b"\r\n")
    for name, (filename, mime, data) in (files or {}).items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        buf.write(f"Content-Type: {mime}\r\n\r\n".encode())
        buf.write(data)
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", buf.getvalue()


class ParseTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        ctype, body = _multipart({"device_id": "g1", "type": "text", "text": "你好"})
        fields, files = parse_multipart(body, ctype)
        self.assertEqual(fields["text"], "你好")
        self.assertFalse(files)

    def test_file(self) -> None:
        ctype, body = _multipart(
            {"device_id": "g1", "type": "image"},
            {"file": ("a.png", "image/png", PNG_1X1)},
        )
        fields, files = parse_multipart(body, ctype)
        self.assertEqual(fields["type"], "image")
        self.assertEqual(files["file"][2], PNG_1X1)

    def test_bad_content_type(self) -> None:
        with self.assertRaises(HttpError) as ctx:
            parse_multipart(b"x", "application/json")
        self.assertEqual(ctx.exception.status, 400)


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.calls: list[str] = []

        def notify(message: str, **_: object) -> tuple[bool, str]:
            self.calls.append(message)
            return True, "收到测试"

        self.app = IngestApp(
            secret="s" * 32,
            media_root=root / "media",
            state_path=root / "idem.json",
            notify=notify,
        )
        self.auth = {"Authorization": "Bearer " + "s" * 32}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _post(self, fields: dict[str, str], files=None):
        ctype, body = _multipart(fields, files)
        headers = {**self.auth, "Content-Type": ctype}
        return self.app.handle("POST", "/rokid-app/v1/inbound", headers, body)

    def test_health_needs_auth(self) -> None:
        st, _, body = self.app.handle("GET", "/rokid-app/v1/health", {}, b"")
        self.assertEqual(st, 401)
        st, _, body = self.app.handle("GET", "/rokid-app/v1/health", self.auth, b"")
        self.assertEqual(st, 200)
        self.assertEqual(body, b"ok\n")

    def test_wrong_secret(self) -> None:
        ctype, raw = _multipart({"device_id": "dev-1", "type": "text", "text": "hi"})
        st, _, _ = self.app.handle(
            "POST",
            "/rokid-app/v1/inbound",
            {"Authorization": "Bearer wrong", "Content-Type": ctype},
            raw,
        )
        self.assertEqual(st, 401)
        self.assertFalse(self.calls)

    def test_text(self) -> None:
        st, _, body = self._post({"device_id": "dev-1", "type": "text", "text": "你好眼镜"})
        self.assertEqual(st, 200)
        self.assertEqual(body.decode(), "收到测试")
        self.assertIn("你好眼镜", self.calls[0])
        self.assertIn("rokid-app-dev-1", session_id_for("dev-1"))

    def test_image_saves(self) -> None:
        st, _, body = self._post(
            {"device_id": "dev-1", "type": "image"},
            {"file": ("shot.png", "image/png", PNG_1X1)},
        )
        self.assertEqual(st, 200)
        self.assertEqual(body.decode(), "收到测试")
        saved = list((Path(self.tmp.name) / "media" / "dev-1").glob("*.png"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), PNG_1X1)
        self.assertIn(str(saved[0].resolve()), self.calls[0])
        self.assertIn("不要 sessions_spawn", self.calls[0])

    def test_audio_saves_and_stays_unwritten(self) -> None:
        st, _, body = self._post(
            {"device_id": "dev-1", "type": "audio"},
            {"file": ("rec-20260902-011500.m4a", "audio/mp4", M4A_STUB)},
        )
        self.assertEqual(st, 200)
        self.assertEqual(body.decode(), "收到测试")
        saved = list((Path(self.tmp.name) / "media" / "dev-1").glob("*.m4a"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), M4A_STUB)
        message = self.calls[0]
        self.assertIn(str(saved[0].resolve()), message)
        self.assertIn("只确认已收到该文件", message)
        self.assertIn("不要转写", message)
        self.assertNotIn("用 image 工具", message)

    def test_unknown_type(self) -> None:
        st, _, body = self._post({"device_id": "dev-1", "type": "pdf", "text": "x"})
        self.assertEqual(st, 400)
        self.assertIn("未知 type", body.decode())

    def test_too_large_file(self) -> None:
        huge = b"x" * (8 * 1024 * 1024 + 1)
        st, _, body = self._post(
            {"device_id": "dev-1", "type": "image"},
            {"file": ("big.jpg", "image/jpeg", huge)},
        )
        self.assertEqual(st, 413)
        self.assertFalse(self.calls)

    def test_idempotent(self) -> None:
        fields = {
            "device_id": "dev-1",
            "type": "text",
            "text": "同一条",
            "client_msg_id": "msg-1",
        }
        self.assertEqual(self._post(fields)[0], 200)
        self.assertEqual(self._post(fields)[0], 200)
        self.assertEqual(len(self.calls), 1)

    def test_gateway_down_keeps_file(self) -> None:
        def down(message: str, **_: object) -> tuple[bool, str]:
            return False, GATEWAY_UNREACHABLE

        self.app.notify = down
        st, _, body = self._post(
            {"device_id": "dev-1", "type": "image"},
            {"file": ("shot.png", "image/png", PNG_1X1)},
        )
        self.assertEqual(st, 200)
        text = body.decode()
        self.assertIn("已存、Agent 未达", text)
        self.assertTrue(list((Path(self.tmp.name) / "media" / "dev-1").glob("*.png")))

    def test_http_413_by_content_length(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address[:2]
        try:
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.putrequest("POST", "/rokid-app/v1/inbound")
            conn.putheader("Authorization", self.auth["Authorization"])
            conn.putheader("Content-Type", "multipart/form-data; boundary=x")
            conn.putheader("Content-Length", str(90 * 1024 * 1024))
            conn.endheaders()
            resp = conn.getresponse()
            self.assertEqual(resp.status, 413)
            resp.read()
            conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


class ExtractTests(unittest.TestCase):
    def test_payloads(self) -> None:
        blob = '{"ok":true,"result":{"payloads":[{"text":"识别到门牌"}]}}'
        self.assertEqual(extract_agent_text(blob), "识别到门牌")

    def test_message_mentions_local_path(self) -> None:
        msg = build_agent_message(
            device_id="g1",
            kind="audio",
            text="",
            path="/tmp/a.m4a",
        )
        self.assertIn("不要转写", msg)
        self.assertIn("/tmp/a.m4a", msg)


if __name__ == "__main__":
    unittest.main()
