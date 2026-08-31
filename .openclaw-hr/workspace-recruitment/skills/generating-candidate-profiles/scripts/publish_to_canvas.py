#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_to_canvas.py — 把候选人画像 HTML 发布到 OpenClaw Canvas host

Skill:    generating-candidate-profiles
用途:     把 validate_profile_html.js 校验通过的 HTML,复制到
          Canvas host 的 documents 目录下,使 HR 能在浏览器中
          (经 Nginx canvas-proxy 反代 18999) 直接访问。

要点 (设计意图详见 references/canvas-publishing.md):

  1. <id> 必须匹配 /^[A-Za-z0-9._-]+$/
       → Canvas 路由 normalizeCanvasDocumentId() 拒绝非 ASCII / 全角 / emoji
  2. 文件名必须固定为 index.html
       → Canvas 路由硬拼 /documents/<id>/index.html
  3. 落盘路径用 $OPENCLAW_STATE_DIR/canvas/documents/,
     不用 workspace 路径
       → Canvas host.root 在 config/openclaw.yaml 里配置, 任意变更
  4. HTML 必须是 UTF-8 无 BOM, 含 <!DOCTYPE html> 与 </html>
       → Nginx sub_filter 锚点 + 浏览器按 HTML 解析
  5. 落盘用 tempfile + atomic rename, 不直接覆盖
  6. 同一目录下已有 index.html 时, 必须显式 --force 才覆盖

CLI:
  python3 publish_to_canvas.py <profile.html> <canvas-id> [--force]
  python3 publish_to_canvas.py <profile1.html> <id1> <profile2.html> <id2> ...

退出码:
  0  = 落盘成功
  1  = 参数错 (EX_USAGE)
  2  = 输入文件错 (EX_NOINPUT)
  3  = 约束校验失败 (EX_DATAERR: id 非法 / HTML 不合法)
  4  = 落盘失败 (EX_IOERR)
  5  = 已有同名文档存在, 需 --force (EX_CANTCREAT)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple


# ---------------------------------------------------------------------------
# 常量: 约束列表 (详见 references/canvas-publishing.md)
# ---------------------------------------------------------------------------

# A. Canvas 路由的硬约束 (normalizeCanvasDocumentId)
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
ID_MAX_LEN = 80

# 路径穿越 / 保留字
RESERVED_IDS = {"documents", ".", "..", ""}

# HTML 完整性检查
DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+html", re.IGNORECASE)
HTML_CLOSE_RE = re.compile(r"</html>", re.IGNORECASE)

# UTF-8 BOM 的字节序
UTF8_BOM = b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# 退出码 (BSD sysexits.h 风格, 让 Agent 能按位分辨)
# ---------------------------------------------------------------------------

EX_OK = 0
EX_USAGE = 1        # 参数错
EX_NOINPUT = 2      # 源 HTML 文件不存在 / 不可读
EX_DATAERR = 3      # 约束校验失败
EX_IOERR = 4        # 落盘失败
EX_CANTCREAT = 5    # 目标已存在, 未开 --force


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def validate_id(canvas_id: str) -> Tuple[bool, str]:
    """校验 canvas-id 是否合法. 返回 (ok, err_msg)."""
    if not canvas_id:
        return False, "id 不能为空"
    if canvas_id in RESERVED_IDS:
        return False, f"id '{canvas_id}' 是 Canvas 保留字, 不可用"
    if canvas_id.startswith("."):
        return False, f"id '{canvas_id}' 不能以 '.' 开头 (路径穿越防御)"
    if ".." in canvas_id:
        return False, f"id '{canvas_id}' 不能含 '..' (路径穿越防御)"
    if len(canvas_id) > ID_MAX_LEN:
        return False, (
            f"id 长度 {len(canvas_id)} > 限 {ID_MAX_LEN} "
            f"(nginx/CDN URL 长度友好上限)"
        )
    if not ID_PATTERN.match(canvas_id):
        # 给具体的字符级提示, 让 Agent 看到就能 fix
        bad_chars = sorted(
            {c for c in canvas_id if not re.match(r"[A-Za-z0-9._-]", c)}
        )
        return False, (
            f"id '{canvas_id}' 含非 ASCII / 全角 / emoji 字符: {bad_chars}. "
            f"Canvas 路由 normalizeCanvasDocumentId() 只接 [A-Za-z0-9._-]. "
            f"约定 ASCII 别名: 'profile-<pinyin-no-tones>', "
            f"如 'profile-zhanglei'."
        )
    return True, ""


def validate_html(path: Path) -> Tuple[bool, str]:
    """校验 HTML 文件: 存在 / 非空 / UTF-8 无 BOM / 含 DOCTYPE 与 </html>."""
    if not path.exists():
        return False, f"HTML 文件不存在: {path}"
    if not path.is_file():
        return False, f"HTML 路径不是文件: {path}"
    try:
        raw = path.read_bytes()
    except OSError as e:
        return False, f"读取 HTML 失败: {e}"

    if len(raw) < 200:
        return False, f"HTML 过短 ({len(raw)} 字节), 疑似生成未完成"

    # BOM
    if raw.startswith(UTF8_BOM):
        return False, (
            "HTML 含 UTF-8 BOM. Nginx sub_filter 锚 </head> 会错位. "
            "请以 UTF-8 无 BOM 重新保存."
        )

    # 解码 (允许 HTML 实体里夹的字节流,我们只看文本层)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, f"HTML 非 UTF-8 编码: {e}"

    # DOCTYPE
    if not DOCTYPE_RE.search(text):
        return False, "HTML 缺 <!DOCTYPE html> 声明 (浏览器会进 quirks mode, CSS flex/grid 失真)"

    # 闭合 </html>
    if not HTML_CLOSE_RE.search(text):
        return False, "HTML 缺 </html> 收尾标记 (Nginx sub_filter 注入锚点可能错位)"

    return True, ""


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------

def resolve_canvas_root() -> Path:
    """从环境解析 Canvas host 根目录, 显式拒绝相对路径."""

    # 优先级: $OPENCLAW_STATE_DIR/canvas > $HOME/.openclaw/canvas > $HOME/.openclaw-hr/canvas
    # 但 skill 编译期已知本 profile 叫 openclaw-hr, 所以默认直接指向 ~/.openclaw-hr/canvas
    state_dir = os.environ.get("OPENCLAW_STATE_DIR", "").strip()
    home = Path.home()

    candidates = []
    if state_dir:
        candidates.append(Path(state_dir) / "canvas")
    candidates.append(home / ".openclaw" / "canvas")
    candidates.append(home / ".openclaw-hr" / "canvas")

    for p in candidates:
        if p.exists() and p.is_dir():
            return p.resolve()

    # 都没创建, 用默认 fallback 显式建空目录
    fallback = home / ".openclaw-hr" / "canvas"
    return fallback.resolve()


def resolve_ports() -> Tuple[int, int]:
    """从环境/nginx 配置推算 gateway + nginx 反代端口.

    优先级: 显式 env > nginx 配置探测 > 文档约定默认值
    """
    # ---- nginx (canvas-proxy) 端口 ----
    nginx_port_env = os.environ.get("NGINX_CANVAS_PORT", "").strip()
    if nginx_port_env:
        nginx_port = int(nginx_port_env)
    else:
        # 从 nginx 配置探测: 扫监听 127.0.0.1 的非 80 端口
        nginx_port = 0  # 0 表示未探测到
        if shutil.which("nginx") and Path("/root/.openclaw-hr/nginx/conf").exists():
            try:
                import subprocess
                # 用 nginx -T 过滤出 listen 行
                out = subprocess.run(
                    ["nginx", "-T", "-c", "/root/.openclaw-hr/nginx/conf/nginx.conf"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                # 找形如 "listen 127.0.0.1:18999" 或 "listen 18999" 的项
                ports = re.findall(
                    r"listen\s+127\.0\.0\.1:(\d+)", out.stdout
                )
                if ports:
                    nginx_port = int(ports[0])
            except Exception:
                pass

    # ---- gateway 端口 ----
    gateway_port_env = os.environ.get("HR_PORT", "").strip()
    if gateway_port_env:
        gateway_port = int(gateway_port_env)
    else:
        gateway_port = 18790  # 文档约定默认值 (HR profile 默认端口)

    return nginx_port, gateway_port


def publish(html_path: Path, canvas_id: str, force: bool) -> Tuple[bool, str]:
    """落盘一份 HTML 到 Canvas host. 返回 (ok, msg)."""

    canvas_root = resolve_canvas_root()
    docs_dir = canvas_root / "documents"
    target = (docs_dir / canvas_id / "index.html").resolve()

    # 防止 resolve 后跨越出 canvas root (symlink 攻击防御)
    try:
        target.relative_to(canvas_root.resolve())
    except ValueError:
        return False, f"目标路径逃出 canvas root: {target} (id 非法?)"

    if not docs_dir.exists():
        try:
            docs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"创建 documents 目录失败: {e}"

    target_dir = target.parent
    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            # 单候选人目录收紧权限 (含 HTML + 接下来要放 PNG/MD 也行)
            os.chmod(target_dir, 0o755)
        except OSError as e:
            return False, f"创建候选人目录失败: {e}"

    # 已有检查
    if target.exists() and not force:
        return (
            False,
            f"目标已存在: {target}. 重发同名 ID 需要显式 --force "
            f"(删除旧文件以防审计追溯不上).",
        )

    # 读取源
    try:
        src_bytes = html_path.read_bytes()
    except OSError as e:
        return False, f"读取源 HTML 失败: {e}"

    # 原子落盘: tempfile + rename
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{canvas_id}.", suffix=".staging", dir=str(target_dir)
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(src_bytes)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # 某些 fs 不支持 fsync, 不阻断
            os.replace(tmp_path, target)
        except Exception:
            # 清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
    except OSError as e:
        return False, f"落盘失败: {e}"

    # 落盘后烟雾回读
    try:
        verify = target.read_bytes()
        if verify != src_bytes:
            return False, "落盘烟雾回读不一致 (磁盘 / fs 异常)"
    except OSError as e:
        return False, f"落盘烟雾回读失败: {e}"

    nginx_port, gateway_port = resolve_ports()
    port_lines = []
    if nginx_port:
        port_lines.append(
            f"  nginx:    http://127.0.0.1:{nginx_port}"
            f"/__openclaw__/canvas/documents/{canvas_id}/index.html"
            f"   (推荐, 浏览器无需 Bearer)"
        )
    port_lines.append(
        f"  gateway:  http://127.0.0.1:{gateway_port}"
        f"/__openclaw__/canvas/documents/{canvas_id}/index.html"
        f"   (需 Bearer)"
    )

    msg = (
        f"  local:    {target}\n"
        f"  size:     {len(src_bytes)} bytes\n"
        + "\n".join(port_lines)
    )
    return True, msg


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="publish_to_canvas.py",
        description="把候选人画像 HTML 发布到 OpenClaw Canvas host.",
        epilog=(
            "约束详见 references/canvas-publishing.md. "
            "ASCII 别名示例: profile-zhanglei / profile-zhouxiaofeng"
        ),
    )
    p.add_argument(
        "pairs",
        nargs="+",
        metavar="PATH_OR_ID",
        help="<profile.html> <canvas-id> [<profile2.html> <id2> ...]",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖目标 documents/<id>/index.html (默认拒绝,防误覆盖)",
    )
    return p.parse_args(argv)


def run_one(html_arg: str, canvas_id: str, force: bool) -> Tuple[int, str]:
    """处理一对. 返回 (exit_code, msg_or_pretty)."""
    html_path = Path(html_arg)

    # ---- [2/9] HTML 文件存在 + 非空 ----
    if not html_path.exists():
        return EX_NOINPUT, f"[2/9] HTML 文件不存在: {html_path}"

    # ---- [3/9] ID 校验 ----
    ok, err = validate_id(canvas_id)
    if not ok:
        return EX_DATAERR, f"[3/9] {err}"

    # ---- [4/9] [5/9] HTML 完整性 ----
    ok, err = validate_html(html_path)
    if not ok:
        return EX_DATAERR, f"[4/9] {err}"

    # ---- [6/9] 路径解析 + [7/9] 目录可写  [9/9] 落盘烟雾回读 ----
    ok, msg = publish(html_path, canvas_id, force)
    if not ok:
        # 区分 IO 错 / 已存在
        if "已存在" in msg:
            return EX_CANTCREAT, f"[8/9] {msg}"
        return EX_IOERR, f"[8/9] {msg}"

    return EX_OK, msg


def main() -> int:
    args = parse_args(sys.argv[1:])

    # ---- [1/9] 参数 ----
    pairs = args.pairs
    if len(pairs) % 2 != 0 or len(pairs) == 0:
        print(
            "用法: python3 publish_to_canvas.py <profile.html> <canvas-id> "
            "[<profile2.html> <id2> ...] [--force]\n"
            "或  : python3 publish_to_canvas.py --help",
            file=sys.stderr,
        )
        return EX_USAGE

    failed = 0
    fail_codes: List[int] = []
    for i in range(0, len(pairs), 2):
        html_arg = pairs[i]
        canvas_id = pairs[i + 1]
        print(f"--- publish: {html_arg} → {canvas_id} ---")
        code, msg = run_one(html_arg, canvas_id, args.force)
        if code == EX_OK:
            print(f"[ok] {msg}")
        else:
            print(f"[FAIL] {msg}", file=sys.stderr)
            failed += 1
            fail_codes.append(code)
        print()

    if failed:
        # 严重度序: EX_NOINPUT(2) < EX_DATAERR(3) < EX_IOERR(4) < EX_CANTCREAT(5)
        # Agent 看到 exit code 就能定位大致失败种类 (无需 scan stderr)
        worst = max(fail_codes) if fail_codes else EX_DATAERR
        print(
            f"[summary] {failed}/{len(pairs) // 2} 个失败, "
            f"最严重 exit={worst}, 请看 stderr 修复.",
            file=sys.stderr,
        )
        return worst
    return EX_OK


if __name__ == "__main__":
    sys.exit(main())
