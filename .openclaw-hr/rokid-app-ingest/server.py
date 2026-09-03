#!/usr/bin/env python3
"""乐奇眼镜独立上传服务：:18791 收 POST，落盘后再 loopback 调 openclaw agent。"""
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
CLIENT_MSG_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
TYPES = frozenset({"text", "image", "audio", "video"})
TEXT_MAX = 8 * 1024
TYPE_MAX = {
    "image": 8 * 1024 * 1024,
    "audio": 20 * 1024 * 1024,
    "video": 80 * 1024 * 1024,
}
MAX_BODY = TYPE_MAX["video"] + 512 * 1024
ALLOWED_MIME = {
    "image": frozenset({"image/jpeg", "image/jpg", "image/webp", "image/png"}),
    "audio": frozenset({"audio/mp4", "audio/aac", "audio/mpeg", "audio/mp3"}),
    "video": frozenset({"video/mp4"}),
}
EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/png": ".png",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "video/mp4": ".mp4",
}
NOTIFY_TIMEOUT_SECONDS = 180
GATEWAY_UNREACHABLE = "已存、Agent 未达"


class HttpError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def parse_multipart(
    body: bytes, content_type: str
) -> tuple[dict[str, str], dict[str, tuple[str, str, bytes]]]:
    ctype = (content_type or "").strip()
    if not ctype.lower().startswith("multipart/form-data"):
        raise HttpError(400, "Content-Type 必须是 multipart/form-data")
    boundary = ""
    for part in ctype.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
            break
    if not boundary:
        raise HttpError(400, "multipart 缺少 boundary")
    try:
        delim = b"--" + boundary.encode("ascii", "strict")
    except UnicodeEncodeError as exc:
        raise HttpError(400, "multipart boundary 非法") from exc
    if delim not in body:
        raise HttpError(400, "multipart 无法按 boundary 拆分")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, str, bytes]] = {}
    chunks = body.split(delim)
    for raw in chunks:
        if not raw or raw in (b"--", b"--\r\n", b"--\n"):
            continue
        if raw.startswith(b"--"):
            continue
        if raw.startswith(b"\r\n"):
            raw = raw[2:]
        elif raw.startswith(b"\n"):
            raw = raw[1:]
        if raw.endswith(b"\r\n"):
            raw = raw[:-2]
        elif raw.endswith(b"\n"):
            raw = raw[:-1]
        sep = b"\r\n\r\n"
        if sep not in raw:
            sep = b"\n\n"
        if sep not in raw:
            continue
        head_b, data = raw.split(sep, 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        elif data.endswith(b"\n"):
            data = data[:-1]
        headers: dict[str, str] = {}
        for line in head_b.replace(b"\r\n", b"\n").split(b"\n"):
            if b":" not in line:
                continue
            k, v = line.split(b":", 1)
            headers[k.decode("latin-1").strip().lower()] = v.decode("latin-1").strip()
        disp = headers.get("content-disposition", "")
        name = _disp_param(disp, "name")
        if not name:
            continue
        filename = _disp_param(disp, "filename")
        mime = (headers.get("content-type") or "application/octet-stream").split(";")[0].strip().lower()
        if filename is not None:
            files[name] = (filename, mime, data)
        else:
            try:
                fields[name] = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HttpError(400, f"字段 {name} 不是 UTF-8") from exc
    return fields, files


def _disp_param(header: str, key: str) -> str | None:
    for piece in header.split(";"):
        piece = piece.strip()
        if "=" not in piece:
            continue
        k, v = piece.split("=", 1)
        if k.strip().lower() == key.lower():
            return v.strip().strip('"')
    return None


def bearer_token(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "bearer" or not rest.strip():
        return None
    return rest.strip()


def auth_ok(got: str | None, expected: str) -> bool:
    if not got or not expected:
        return False
    left, right = got.encode("utf-8"), expected.encode("utf-8")
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def session_id_for(device_id: str) -> str:
    return f"rokid-app-{device_id}"


def build_agent_message(
    *,
    device_id: str,
    kind: str,
    text: str,
    path: str | None,
) -> str:
    lines = [
        "【乐奇眼镜上传】",
        f"device_id={device_id}",
        f"type={kind}",
    ]
    if path:
        lines.append(f"本地绝对路径={path}")
    if kind == "image":
        lines.extend(
            [
                "用 image 工具读取上面的本地文件。不要 web_fetch，不要填任何 OSS URL。",
                "这不是招聘/入职/培训/绩效/行政任务，不要 sessions_spawn。",
                "用简短中文回复眼镜用户。",
            ]
        )
        if text:
            lines.append("用户附言：")
            lines.append(text)
    elif kind in {"audio", "video"}:
        lines.extend(
            [
                "本机 ASR 尚未开通。只确认已收到该文件。",
                "不要转写、不要抽帧、不要编造纪要，不要 sessions_spawn。",
            ]
        )
        if text:
            lines.append("用户附言：")
            lines.append(text)
    else:
        lines.append("用户原文（按原文判域；只有明确是五域 HR 业务才 sessions_spawn）：")
        lines.append(text)
    return "\n".join(lines)


def extract_agent_text(blob: str) -> str:
    raw = blob.strip()
    if not raw:
        return ""
    start = raw.find("{")
    if start < 0:
        return raw
    try:
        data = json.loads(raw[start:])
    except json.JSONDecodeError:
        return raw
    if not isinstance(data, dict):
        return raw
    result = data.get("result") if isinstance(data.get("result"), dict) else data
    payloads = result.get("payloads") if isinstance(result, dict) else None
    texts: list[str] = []
    if isinstance(payloads, list):
        for item in payloads:
            if isinstance(item, dict) and item.get("text"):
                texts.append(str(item["text"]))
            elif isinstance(item, str) and item.strip():
                texts.append(item)
    if texts:
        return "\n".join(texts).strip()
    for key in ("text", "reply", "summary"):
        val = result.get(key) if isinstance(result, dict) else None
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def notify_via_openclaw_agent(
    message: str,
    *,
    device_id: str,
    timeout_seconds: int = NOTIFY_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    binary = shutil.which("openclaw")
    if not binary:
        return False, GATEWAY_UNREACHABLE + "（找不到 openclaw）"
    sid = session_id_for(device_id)
    argv = [
        binary,
        "agent",
        "--agent",
        "router",
        "--session-id",
        sid,
        "--json",
        "--timeout",
        str(timeout_seconds),
        "-m",
        message,
    ]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 40,
            env=dict(env if env is not None else os.environ),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, GATEWAY_UNREACHABLE + "（等待 Agent 超时）"
    except OSError:
        return False, GATEWAY_UNREACHABLE
    stdout = proc.stdout or ""
    text = extract_agent_text(stdout)
    if proc.returncode != 0 and not text:
        err = (proc.stderr or "").strip().splitlines()
        hint = err[-1] if err else f"exit {proc.returncode}"
        return False, f"{GATEWAY_UNREACHABLE}（{hint}）"
    if not text:
        return True, "Agent 已处理，但回复为空。"
    return True, text


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            data = self._load()
            item = data.get(key)
            if isinstance(item, dict) and isinstance(item.get("reply"), str):
                return item["reply"]
            return None

    def put(self, key: str, reply: str) -> None:
        with self._lock:
            data = self._load()
            data[key] = {"reply": reply}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
            tmp.replace(self.path)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}


class IngestApp:
    def __init__(
        self,
        *,
        secret: str,
        media_root: Path,
        state_path: Path,
        notify: Callable[..., tuple[bool, str]] | None = None,
        timeout_seconds: int = NOTIFY_TIMEOUT_SECONDS,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not secret:
            raise ValueError("ROKID_APP_INGEST_SECRET 未设置")
        self.secret = secret
        self.media_root = media_root
        self.store = IdempotencyStore(state_path)
        self.notify = notify or notify_via_openclaw_agent
        self.timeout_seconds = timeout_seconds
        self.env = env

    def handle(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: bytes,
    ) -> tuple[int, str, bytes]:
        route = urlparse(path).path.rstrip("/") or "/"
        token = bearer_token(headers.get("Authorization") or headers.get("authorization"))
        if not auth_ok(token, self.secret):
            return 401, "text/plain; charset=utf-8", "unauthorized\n".encode("utf-8")
        if route == "/rokid-app/v1/health":
            if method not in {"GET", "HEAD"}:
                return 405, "text/plain; charset=utf-8", "method not allowed\n".encode("utf-8")
            return 200, "text/plain; charset=utf-8", b"ok\n"
        if route != "/rokid-app/v1/inbound":
            return 404, "text/plain; charset=utf-8", "not found\n".encode("utf-8")
        if method != "POST":
            return 405, "text/plain; charset=utf-8", "method not allowed\n".encode("utf-8")
        try:
            text = self._inbound(headers, body)
        except HttpError as exc:
            return exc.status, "text/plain; charset=utf-8", (exc.message + "\n").encode("utf-8")
        return 200, "text/plain; charset=utf-8", text.encode("utf-8")

    def _inbound(self, headers: Mapping[str, str], body: bytes) -> str:
        ctype = headers.get("Content-Type") or headers.get("content-type") or ""
        fields, files = parse_multipart(body, ctype)
        device_id = (fields.get("device_id") or "").strip()
        kind = (fields.get("type") or "").strip().lower()
        text = fields.get("text") or ""
        client_msg_id = (fields.get("client_msg_id") or "").strip()
        if not DEVICE_ID_RE.match(device_id):
            raise HttpError(400, "device_id 非法")
        if kind not in TYPES:
            raise HttpError(400, "未知 type")
        if len(text.encode("utf-8")) > TEXT_MAX:
            raise HttpError(400, "text 超过 8KiB")
        if client_msg_id and not CLIENT_MSG_ID_RE.match(client_msg_id):
            raise HttpError(400, "client_msg_id 非法")
        if kind == "text":
            if not text.strip():
                raise HttpError(400, "type=text 时 text 必填")
            saved_path = None
        else:
            if "file" not in files:
                raise HttpError(400, "缺少 file")
            filename, mime, data = files["file"]
            if not data:
                raise HttpError(400, "file 为空")
            if len(data) > TYPE_MAX[kind]:
                raise HttpError(413, "file 超过该 type 上限")
            if mime not in ALLOWED_MIME[kind]:
                raise HttpError(400, f"不支持的 MIME: {mime}")
            saved_path = self._save_file(device_id, kind, mime, filename, data)

        idem_key = f"{device_id}:{client_msg_id}" if client_msg_id else ""
        if idem_key:
            cached = self.store.get(idem_key)
            if cached is not None:
                return cached

        message = build_agent_message(
            device_id=device_id,
            kind=kind,
            text=text.strip(),
            path=str(saved_path) if saved_path else None,
        )
        notify_kw: dict[str, Any] = {
            "device_id": device_id,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.env is not None:
            notify_kw["env"] = self.env
        ok, reply = self.notify(message, **notify_kw)
        if saved_path is not None and not ok:
            reply = f"{reply}\npath={saved_path}"
        elif not ok and kind == "text":
            reply = reply
        if idem_key:
            self.store.put(idem_key, reply)
        return reply

    def _save_file(
        self,
        device_id: str,
        kind: str,
        mime: str,
        filename: str,
        data: bytes,
    ) -> Path:
        ext = EXT_BY_MIME.get(mime)
        if not ext:
            suffix = Path(filename or "").suffix.lower()
            ext = suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".m4a", ".aac", ".mp3", ".mp4"} else f".{kind}"
        stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
        dest_dir = self.media_root / device_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{stamp}-{uuid.uuid4().hex}{ext}"
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
        return dest.resolve()


def _header_map(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    return {k: v for k, v in handler.headers.items()}


def make_handler(app: IngestApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: object) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self) -> None:
            self._dispatch(b"")

        def do_HEAD(self) -> None:
            self._dispatch(b"", head=True)

        def do_POST(self) -> None:
            length = self.headers.get("Content-Length")
            if self.path.split("?", 1)[0].rstrip("/") == "/rokid-app/v1/inbound":
                if length is None:
                    self._send(411, "text/plain; charset=utf-8", b"length required\n")
                    return
                try:
                    n = int(length)
                except ValueError:
                    self._send(400, "text/plain; charset=utf-8", b"bad content-length\n")
                    return
                if n > MAX_BODY:
                    self._send(413, "text/plain; charset=utf-8", b"payload too large\n")
                    return
                body = self.rfile.read(n) if n else b""
            else:
                n = int(length or "0")
                body = self.rfile.read(n) if n else b""
            self._dispatch(body)

        def _dispatch(self, body: bytes, head: bool = False) -> None:
            status, ctype, out = app.handle(self.command if not head else "HEAD", self.path, _header_map(self), body)
            self._send(status, ctype, out, head=head)

        def _send(self, status: int, ctype: str, body: bytes, head: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)

    return Handler


def profile_dir() -> Path:
    state = os.environ.get("OPENCLAW_STATE_DIR")
    if state:
        return Path(state)
    return Path(__file__).resolve().parents[1]


def main() -> int:
    secret = os.environ.get("ROKID_APP_INGEST_SECRET", "").strip()
    if not secret:
        print("rokid-app-ingest: ROKID_APP_INGEST_SECRET 未设置", file=sys.stderr)
        return 1
    host = os.environ.get("ROKID_APP_INGEST_HOST", "0.0.0.0")
    port = int(os.environ.get("ROKID_APP_INGEST_PORT", "18791"))
    profile = profile_dir()
    media_root = profile / "workspace-router" / "media" / "rokid-app"
    state_path = media_root / "_state" / "idempotency.json"
    timeout = int(os.environ.get("ROKID_APP_NOTIFY_TIMEOUT_SECONDS", str(NOTIFY_TIMEOUT_SECONDS)))
    app = IngestApp(
        secret=secret,
        media_root=media_root,
        state_path=state_path,
        timeout_seconds=timeout,
    )
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"rokid-app-ingest listening on http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
