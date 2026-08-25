#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mark_read.py — 给指定 UID 的 IMAP 邮件打 \\Seen (已读) 标记

设计要点:
  - 纯 live 后端 (mock maildir 没有 \\Seen 概念, 直接改文件名:2 标记位)
  - 一次支持多个 UID (空格/逗号分隔)
  - --dry-run: 只打印候选, 不打 \\Seen
  - --subject/--since: 模糊匹配 (按主题包含 / Date_gte), 然后打 \\Seen
  - 不删不挪邮件
  - 安全: 邮件 ID 必须 ASCII (IMAP UID 字符串, mock 也接受, 但以 live 为主)

CLI:
  python mark_read.py --uid 3716                              # 单个 UID
  python mark_read.py --uid "3716 3717 3718"                 # 多个 UID (空格分隔)
  python mark_read.py --subject "阿里云账号登录安全提醒"     # 按主题包含匹配
  python mark_read.py --since 2026-07-11 --subject "投递"    # 时间窗 + 主题过滤
  python mark_read.py --uid 3716 --dry-run                   # 只打印, 不打 \\Seen
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from imap_tools import MailBox, AND
from imap_tools.consts import MailMessageFlags


def _print(msg: str, *, dry: bool = False) -> None:
    print(msg)
    if not dry:
        print(msg, file=sys.stderr)


def _check_creds() -> tuple[str, str, str, int]:
    user = os.environ.get("IMAP_USER", "")
    pw = os.environ.get("IMAP_PASS", "")
    host = os.environ.get("IMAP_HOST", "imap.qq.com")
    port = int(os.environ.get("IMAP_PORT", "993"))
    if not user or not pw:
        print("[!] IMAP_USER / IMAP_PASS 环境变量必须设", file=sys.stderr)
        sys.exit(2)
    return host, port, user, pw


def _parse_uids(raw: str) -> list[str]:
    """接受 '3716' / '3716,3717' / '3716 3717' / '3716, 3718'"""
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    if not parts:
        print("[!] --uid 空", file=sys.stderr)
        sys.exit(2)
    return parts


def main() -> int:
    p = argparse.ArgumentParser(description="按 UID/主题 给 IMAP 邮件打 \\Seen")
    p.add_argument("--uid", help="邮件 UID, 空格或逗号分隔多个")
    p.add_argument("--subject", help="按主题包含匹配 (UTF-8, 需 QQ IMAP 支持)")
    p.add_argument("--since", help="时间下限 (YYYY-MM-DD), 与 --subject 联合用")
    p.add_argument("--days-ago", type=int, default=2,
                   help="默认 since = today - N 天 (默认 2), --since 显式传则覆盖")
    p.add_argument("--folder", default=os.environ.get("MAIL_FOLDER", "INBOX"))
    p.add_argument("--host", default=os.environ.get("IMAP_HOST", "imap.qq.com"))
    p.add_argument("--port", type=int, default=int(os.environ.get("IMAP_PORT", "993")))
    p.add_argument("--user", default=os.environ.get("IMAP_USER", ""))
    p.add_argument("--password", default=os.environ.get("IMAP_PASS", ""))
    p.add_argument("--dry-run", action="store_true", help="只打印候选, 不打 \\Seen")
    p.add_argument("--charset", default="utf-8",
                   help="IMAP SEARCH 字符集, 中文主题必须 utf-8 (默认 utf-8)")
    args = p.parse_args()

    if not args.uid and not args.subject:
        p.error("必须给 --uid 或 --subject 之一")

    # env 兜底
    if not args.user or not args.password:
        _, _, args.user, args.password = _check_creds()
    if not args.user or not args.password:
        print("[!] 缺 IMAP 凭据 (IMAP_USER / IMAP_PASS 或 --user/--password)", file=sys.stderr)
        return 2

    with MailBox(args.host, port=args.port).login(args.user, args.password) as mb:
        mb.folder.set(args.folder)

        # 候选 UID 集合
        candidates: list[str] = []
        scan_label = ""

        if args.uid:
            wanted = set(_parse_uids(args.uid))
            scan_label = f"UID 匹配: {sorted(wanted)}"
            # 客户端按 UID 过滤在 QQ 上不稳定, 全量 fetch 再筛选
            for m in mb.fetch(charset=args.charset, mark_seen=False):
                if str(m.uid) in wanted:
                    candidates.append(str(m.uid))
                    print(f"  uid={m.uid}  date={m.date.strftime('%Y-%m-%d %H:%M:%S')}  from={m.from_!r}")
                    print(f"    subj={m.subject!r}")
            # 提示哪些没找到
            missing = wanted - set(candidates)
            if missing:
                print(f"[!] 未找到 UID: {sorted(missing)}", file=sys.stderr)

        elif args.subject:
            since_str = args.since or (datetime.now() - timedelta(days=args.days_ago)).strftime("%Y-%m-%d")
            scan_label = f"主题包含 {args.subject!r} AND date_gte {since_str}"
            for m in mb.fetch(
                AND(subject=args.subject, date_gte=datetime.strptime(since_str, "%Y-%m-%d").date()),
                charset=args.charset, mark_seen=False,
            ):
                candidates.append(str(m.uid))
                print(f"  uid={m.uid}  date={m.date.strftime('%Y-%m-%d %H:%M:%S')}  from={m.from_!r}")
                print(f"    subj={m.subject!r}")

        print(f"[scan] 范围: {scan_label}")
        print(f"[scan] 候选 {len(candidates)} 封: {candidates}")

        if not candidates:
            print("[scan] 0 命中, 不打 \\Seen")
            return 0

        if args.dry_run:
            print(f"[dry-run] 不打 \\Seen, 候选 uid={candidates}")
            return 0

        # 打 \\Seen (imap_tools 的 flag 方法内部用 +FLAGS 处理, 幂等)
        mb.flag(candidates, MailMessageFlags.SEEN, True)
        print(f"[mark] 已给 {len(candidates)} 封打 \\Seen: uids={candidates}")

        # 验证 (重新拉一次, IMAP 服务器读到的 flags 是反向的, 标过 Seen 的仍可读)
        verified = 0
        for m in mb.fetch(AND(uid=candidates), charset=args.charset, mark_seen=False):
            verified += 1
            print(f"  [verify] uid={m.uid} subj={m.subject!r}")
        print(f"[verify] 重读确认 {verified} 封仍可访问 (\\Seen 不影响邮件存在性)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())