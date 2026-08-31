#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_mock_mailbox.py — 把 inbox-test/ 里的简历文件包装成 .eml 投递邮件

测试目标：跑 fetch_resumes.py --backend mock 时，
  1. mailbox/Maildir/cur/ 里有一批 .eml 文件
  2. 每封邮件带一个附件 = inbox-test/ 里的简历
  3. .eml Subject/From/Date 形似真投递（招聘网站投递邮件模板）

不走 SMTP/IMAP 服务器，纯本地 maildir，零网络依赖。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from fetch_resumes import MailBackend  # noqa: F401  触发路径里需要它已 import


def is_resume_attachment(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".md", ".rtf", ".html", ".zip", ".txt"}


def guess_candidate_name(p: Path) -> str:
    # 文件名形如  resume-function-01-候选人F-财务.md → 候选人F
    m = re.search(r"-\d{2}-(.+?)-", p.name)
    return m.group(1) if m else p.stem


def guess_position(p: Path) -> str:
    # 文件名最后 "-" 后是岗位
    stem = p.stem
    parts = stem.rsplit("-", 1)
    return parts[1] if len(parts) == 2 else parts[0]


def build_eml(attachment: Path, *, sender_name: str, sender_email: str, subject: str, sent_offset_min: int) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = "hr-recruit@xingqiao-tech.com"
    msg["Subject"] = subject
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["Message-ID"] = f"<{int(datetime.now().timestamp()*1000)}-{sender_email.replace('@', '.')}@xingqiao-recruit-bot>"

    body = (
        f"HR 您好：\n\n"
        f"我叫 {sender_name}，看到贵司 {subject.split('|')[0].strip()} 岗位在招，"
        f"随信附上简历，盼复。\n\n"
        f"联系方式：\n"
        f"  邮箱：{sender_email}\n"
        f"  附件：{attachment.name}\n\n"
        f"—— {sender_name}\n"
    )
    msg.set_content(body)

    suffix = attachment.suffix.lower()
    ctype_map = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".md": "text/markdown", ".rtf": "application/rtf", ".html": "text/html",
                 ".zip": "application/zip", ".txt": "text/plain"}
    ctype = ctype_map.get(suffix, "application/octet-stream")
    msg.add_attachment(attachment.read_bytes(), maintype=ctype.split("/")[0], subtype=ctype.split("/")[1],
                       filename=attachment.name)
    return msg.as_bytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox-src", default="./inbox-test",
                        help="简历源目录（要被装进邮件附件）")
    parser.add_argument("--mailbox-dir", default="./mailbox",
                        help="生成的 maildir 根目录")
    parser.add_argument("--max-emails", type=int, default=6,
                        help="最多造几封 .eml，0 = 全部简历都装一封")
    parser.add_argument("--clean", action="store_true", help="先清空现有 maildir")
    args = parser.parse_args()

    inbox_src = Path(args.inbox_src).resolve()
    mailbox_dir = Path(args.mailbox_dir).resolve()
    cur_dir = mailbox_dir / "Maildir" / "cur"

    if args.clean and mailbox_dir.exists():
        import shutil
        shutil.rmtree(mailbox_dir)
    cur_dir.mkdir(parents=True, exist_ok=True)

    if not inbox_src.exists():
        print(f"[seed] inbox-src {inbox_src} 不存在；至少放一份示例简历到 ./inbox-test/", file=sys.stderr)
        return 2

    resumes = sorted([p for p in inbox_src.iterdir() if is_resume_attachment(p)])
    if args.max_emails:
        resumes = resumes[: args.max_emails]

    if not resumes:
        print(f"[seed] inbox-src {inbox_src} 里没有简历附件可装", file=sys.stderr)
        return 2

    print(f"[seed] 把 {len(resumes)} 份简历装进 maildir: {cur_dir}")

    for i, resume in enumerate(resumes):
        name = guess_candidate_name(resume)
        position = guess_position(resume)

        # 邮箱形如 zhangyaqin.candidate@example.com - 唯一性是测试需要的
        ascii_name = re.sub(r"[^a-zA-Z]", "", (name or f"cand{i}").lower())[:14] or f"cand{i}"
        sender_email = f"{ascii_name}.{i+1:02d}@example.com"
        sender_name = name or f"候选人{i+1}"
        subject = f"{position} | {name or '应聘者'} 投递"

        # 分布到最近 7 天上, 体现 --since 这个 query
        offset_minutes = i * 60  # 第 i 封: 距今 i 小时前
        sent_date = datetime.now(timezone.utc).timestamp() - offset_minutes * 60
        eml_bytes = build_eml(resume, sender_name=sender_name, sender_email=sender_email, subject=subject,
                              sent_offset_min=offset_minutes)

        eml_name = f"{int(sent_date)}.M{i}P{resume.suffix.replace('.', '').lower()}U.{i}:2,S"
        (cur_dir / eml_name).write_bytes(eml_bytes)
        print(f"[seed]   {eml_name}  ← {resume.name}  ({len(eml_bytes)} bytes)")

    print(f"[seed] 完成, 生成 {len(resumes)} 封邮件, fetch_resumes.py --backend mock --mailbox-dir {mailbox_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
