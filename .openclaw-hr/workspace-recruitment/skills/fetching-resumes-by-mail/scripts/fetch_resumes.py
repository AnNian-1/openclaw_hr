#!/usr/local/miniconda3/envs/py312/bin/python3
# -*- coding: utf-8 -*-
"""
fetch_resumes.py — 收件箱拉简历附件 → 落盘到 ./inbox（仅保留 PDF/DOCX；ZIP/RAR 解压后再提）

设计原则（v2.1）：
  1. 附件白名单（按后缀 + Magic Number 二次校验）：
       pdf, docx, zip, rar
     其他后缀（png/jpg/html/md/txt/...）一律丢弃，**不写盘**。
  2. ZIP/RAR 必须解压缩，**只从中提取 pdf / docx**；其余成员（jpg/htm/...）丢弃。
  3. 姓名 / 岗位识别：**v2.2 起只读简历文件正文**（PDF/DOCX 抽文本 → LLM）。
     **不看**邮件主题 / 正文 / 附件文件名（避免「张三简历投送」但 PDF 实为张磊 这类误导）。
     LLM 为默认（DeepSeek V4 Flash）；--no-llm 时对抽出的正文做启发式。
     缓存 key = 文件内容 sha256，同内容不重复调。
  4. 重命名：统一「姓名-岗位.ext」；若 inbox 已存在**同姓名**文件则跳过落盘（不覆盖）
  5. 安全护栏：zip-slip / 单附件 ≤ 50MB / 单压缩包解压 ≤ 200MB / 解压成员 ≤ 1000 / 压缩比 ≤ 100x / rar 嵌套不展开
  6. 不假设比 HR 会管邮件：不删不挪原邮件；fetch_resumes.py 不标 \\Seen。
  7. 元数据 .fetched-mail.jsonl 字段：saved_files / skipped_files / reason (含识别 method) / sha256。

CLI:
  python fetch_resumes.py [--backend mock|live] [--inbox-dir DIR] [--folder ...] [--max N] [--dry-run]
                          [--since YYYY-MM-DD]       # 显式覆盖 --days-ago
                          [--days-ago N]             # 默认 2, 拉今天往前 N 天未读邮件
                          [--max-archive-mb 200] [--max-file-mb 50] [--max-ratio 100]
                          [--no-llm]                  # 关闭 LLM, 用启发式 (不推荐)
                          [--llm-model NAME]          # 默认 deepseek-v4-flash
                          [--llm-base-url URL]        # 默认 https://api.deepseek.com
                          [--llm-api-key KEY]         # 默认读 env DEEPSEEK_API_KEY
                          [--llm-timeout SEC]         # 默认 8s
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


# ============================================================
# 常量：白名单 + Magic Number
# ============================================================
ALLOWED_EXTS = {".pdf", ".docx", ".zip", ".rar"}
RESUME_EXTS = {".pdf", ".docx"}
ARCHIVE_EXTS = {".zip", ".rar"}

# Magic Number（文件头）
MAGIC_PDF = b"%PDF-"
MAGIC_DOCX = b"PK\x03\x04"          # docx 也是 zip
MAGIC_ZIP = b"PK\x03\x04"
MAGIC_RAR4 = b"Rar!\x1a\x07\x00"
MAGIC_RAR5 = b"Rar!\x1a\x07\x01\x00"

# 启发式：姓名 / 岗位关键词（用于从主题或原文件抽）
POSITION_KEYWORDS = (
    "工程师", "开发", "架构", "算法", "测试", "运维", "运营", "产品", "设计",
    "HRBP", "HR", "招聘", "财务", "法务", "市场", "销售", "行政", "内容", "用户", "活动",
    "客户", "项目", "数据", "前端", "后端", "全栈", "SRE", "QA", "UI", "UX",
    "经理", "总监", "主管", "专员", "助理", "实习生",
)
# 中文姓名启发：2-4 字中文姓名, 但排除常见动词/名词
NAME_STOPWORDS = {
    # 通用动词/名词, 不可能是姓名
    "简历", "投送", "投递", "附件", "招聘", "应聘", "求职", "面试", "工作", "经验",
    "项目", "开发", "测试", "运营", "设计", "产品", "销售", "市场", "财务", "HRBP",
    "工程师", "经理", "总监", "助理", "专员", "实习生", "后端", "前端", "全栈",
    "算法", "架构", "运维", "数据", "客户", "活动", "内容", "用户", "行政", "法务",
    "新增", "查看", "下载", "邮箱", "来信", "附上", "请查", "您好",
}
NAME_HINT_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}")


# ============================================================
# 后端抽象：mock (本地 maildir) 和 live (QQ IMAP) 共享接口
# ============================================================
@dataclass
class MailAttachment:
    filename: str
    raw_bytes: bytes
    content_type: str

    def sha256_hex(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


@dataclass
class MailSummary:
    subject: str
    sender: str
    date: str
    uid: str
    body: str = ""                       # 邮件正文纯文本(给 LLM 用), 默认空
    attachments: List[MailAttachment] = field(default_factory=list)


class MailBackend:
    name: str = "abstract"

    def list_messages(self, folder: str, since: Optional[str] = None) -> Iterable[MailSummary]:
        raise NotImplementedError

    @staticmethod
    def _decode_header_value(raw: Optional[str]) -> str:
        if not raw:
            return ""
        try:
            decoded = str(make_header(decode_header(raw)))
        except Exception:
            return raw
        return decoded

    @staticmethod
    def _safe_filename(name: str, fallback: str = "attachment") -> str:
        name = (name or "").strip()
        if not name:
            return fallback
        # 清掉 path separator + control chars + NUL
        name = re.sub(r"[\\/]+", "_", name)
        name = re.sub(r"\x00", "", name)
        if name in (".", ".."):
            return fallback
        # 去 windows 保留字前缀 (CON/PRN/AUX/NUL/COM1..9/LPT1..9)
        stem = Path(name).stem.upper()
        if stem in {"CON", "PRN", "AUX", "NUL"} or re.match(r"^(COM|LPT)[1-9]$", stem):
            name = "_" + name
        return name[:240]


# ============================================================
# 后端：mock — 从 ./mailbox/ 目录读取 .eml 文件
# ============================================================
class MockMailBackend(MailBackend):
    name = "mock"

    def __init__(self, mailbox_dir: Path):
        self.mailbox_dir = mailbox_dir

    def list_messages(self, folder: str, since: Optional[str] = None) -> Iterable[MailSummary]:
        from email import message_from_bytes

        cur_dir = self.mailbox_dir / "Maildir" / "cur"
        if not cur_dir.exists():
            print(f"[mock] WARN  {cur_dir} 不存在；先跑 seed_mock_mailbox.py", file=sys.stderr)
            return

        for eml_path in sorted(cur_dir.iterdir()):
            if not eml_path.is_file():
                continue
            try:
                raw = eml_path.read_bytes()
            except Exception as e:
                print(f"[mock] 读取 {eml_path.name} 失败: {e}", file=sys.stderr)
                continue

            msg = message_from_bytes(raw, policy=policy.default)
            summary = self._summary_from_msg(msg, uid=eml_path.name)
            if since and summary.date and summary.date < since:
                continue
            yield summary

    def _summary_from_msg(self, msg: EmailMessage, uid: str) -> MailSummary:
        subj = self._decode_header_value(msg.get("Subject", ""))
        sender = self._decode_header_value(msg.get("From", ""))
        date_raw = msg.get("Date", "")
        try:
            dt = parsedate_to_datetime(date_raw)
            date_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            date_str = date_raw

        attachments: List[MailAttachment] = []
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue
            fname = part.get_filename() or f"part-{len(attachments)}"
            fname = self._safe_filename(self._decode_header_value(fname))
            try:
                payload = part.get_payload(decode=True)
            except Exception as e:
                print(f"[mock] 解码 {fname} 失败: {e}", file=sys.stderr)
                continue
            if payload is None:
                continue
            attachments.append(
                MailAttachment(
                    filename=fname,
                    raw_bytes=payload,
                    content_type=part.get_content_type(),
                )
            )

        # 邮件正文(纯文本, 给 LLM 兜底用)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    continue
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_content() or ""
                    except Exception:
                        body = ""
                    break
        else:
            try:
                body = msg.get_content() or ""
            except Exception:
                body = ""

        return MailSummary(
            subject=subj, sender=sender, date=date_str, uid=uid, body=body, attachments=attachments,
        )


# ============================================================
# 后端：live — 走 imap-tools 连 QQ 邮箱
# ============================================================
class LiveImapBackend(MailBackend):
    name = "live"

    def __init__(self, host: str, port: int, user: str, password: str, ssl: bool = True):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.ssl = ssl

    def list_messages(self, folder: str, since: Optional[str] = None) -> Iterable[MailSummary]:
        try:
            from imap_tools import MailBox, AND
        except ImportError:
            print("[live] imap-tools 未安装，跑 pip install imap-tools", file=sys.stderr)
            return

        if not self.ssl:
            print("[live] WARN  imap-tools 默认走 SSL 993, --no-ssl 仅作语义标志, 实际仍用 SSL", file=sys.stderr)
        with MailBox(self.host, port=self.port).login(self.user, self.password) as mb:
            mb.folder.set(folder)
            crit = AND(seen=False)
            if since:
                # since 可能是 'YYYY-MM-DD' 字符串或 datetime.date, 统一转成 date
                if isinstance(since, str):
                    since = datetime.strptime(since, "%Y-%m-%d").date()
                crit = AND(seen=False, date_gte=since)
            for m in mb.fetch(criteria=crit, mark_seen=False):
                attachments = []
                for att in m.attachments:
                    fname = self._safe_filename(att.filename or "attachment")
                    if not fname:
                        continue
                    attachments.append(
                        MailAttachment(
                            filename=fname,
                            raw_bytes=att.payload,
                            content_type=att.content_type or mimetypes.guess_type(fname)[0] or "application/octet-stream",
                        )
                    )
                yield MailSummary(
                    subject=m.subject or "",
                    sender=m.from_ or "",
                    date=(m.date or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    uid=str(m.uid),
                    body=m.text or "",
                    attachments=attachments,
                )


# ============================================================
# 鲁棒附件处理：白名单 + Magic + 解压 + 安全护栏 + 重命名
# ============================================================
@dataclass
class SavedFile:
    saved_name: str
    source: str                # direct | zip | rar
    orig_name: str
    size: int
    sha256: str
    reason: str = ""           # 落盘原因/解释（保存到 jsonl）


@dataclass
class SkippedFile:
    orig_name: str
    reason: str                # ext-not-allowed | magic-mismatch | too-large | zip-bomb | ...
    size: int = 0


def _ext(name: str) -> str:
    return Path(name).suffix.lower()


def _magic_matches(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(MAGIC_PDF)
    if ext == ".docx" or ext == ".zip":
        return head.startswith(MAGIC_ZIP)
    if ext == ".rar":
        return head.startswith(MAGIC_RAR4) or head.startswith(MAGIC_RAR5)
    return False


# ---------- ZIP 解压（含安全护栏） ----------
def _safe_extract_zip(buf: bytes, *, max_total_mb: int, max_files: int, max_ratio: int) -> List[Tuple[str, bytes]]:
    """返回 [(内层文件名, 字节), ...]; 过滤 zip-slip / bomb / 越界 / 过大。"""
    out: List[Tuple[str, bytes]] = []
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(buf)) as zf:
            infos = zf.infolist()
            if len(infos) > max_files:
                raise ValueError(f"zip contains {len(infos)} entries > limit {max_files}")
            compressed_total = sum(i.compress_size for i in infos)
            uncompressed_total = sum(i.file_size for i in infos)
            if compressed_total > 0 and uncompressed_total / compressed_total > max_ratio:
                raise ValueError(
                    f"zip bomb suspected: ratio {uncompressed_total/compressed_total:.1f}x > limit {max_ratio}x"
                )
            if uncompressed_total > max_total_mb * 1024 * 1024:
                raise ValueError(f"zip uncompressed size {uncompressed_total} > limit {max_total_mb*1024*1024}")
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename
                # 防 zip-slip
                norm = os.path.normpath(name)
                if norm.startswith("..") or os.path.isabs(norm) or "\\" in name.replace("/", ""):
                    raise ValueError(f"zip-slip blocked: {name!r}")
                # 解压
                try:
                    data = zf.read(info)
                except RuntimeError as e:
                    print(f"[zip] 跳过加密或损坏成员 {name}: {e}", file=sys.stderr)
                    continue
                if info.file_size > max_total_mb * 1024 * 1024:
                    print(f"[zip] 跳过超大成员 {name} ({info.file_size} bytes)", file=sys.stderr)
                    continue
                total += len(data)
                out.append((os.path.basename(name), data))
                if total > max_total_mb * 1024 * 1024:
                    raise ValueError(f"zip extracted size > limit {max_total_mb} MB")
    except zipfile.BadZipFile as e:
        raise ValueError(f"bad zip: {e}") from None
    return out


# ---------- RAR 解压（可选依赖 rarfile；缺则跳过 rar） ----------
def _safe_extract_rar(buf: bytes, *, max_total_mb: int, max_files: int, max_ratio: int) -> List[Tuple[str, bytes]]:
    try:
        import rarfile  # type: ignore
    except ImportError:
        raise ValueError("rarfile not installed; pip install rarfile (and unrar on PATH)")

    out: List[Tuple[str, bytes]] = []
    total = 0
    with rarfile.RarFile(io.BytesIO(buf)) as rf:
        infos = rf.infolist()
        if len(infos) > max_files:
            raise ValueError(f"rar contains {len(infos)} entries > limit {max_files}")
        # rar 的 compress/uncompress size 不一定可靠, 只看 total
        uncompressed_total = sum(i.file_size for i in infos if not i.is_dir())
        if uncompressed_total > max_total_mb * 1024 * 1024:
            raise ValueError(f"rar uncompressed size {uncompressed_total} > limit")
        for info in infos:
            if info.is_dir():
                continue
            name = info.filename
            norm = os.path.normpath(name)
            if norm.startswith("..") or os.path.isabs(norm) or "\\" in name.replace("/", ""):
                raise ValueError(f"rar-slip blocked: {name!r}")
            # rar 嵌套: 不展开（这里是兜底, 不允许再含 rar/zip）
            inner_ext = _ext(name)
            if inner_ext in ARCHIVE_EXTS:
                print(f"[rar] 跳过嵌套压缩包 {name}", file=sys.stderr)
                continue
            data = rf.read(info)
            total += len(data)
            out.append((os.path.basename(name), data))
            if total > max_total_mb * 1024 * 1024:
                raise ValueError(f"rar extracted size > limit {max_total_mb} MB")
    return out


# ---------- 姓名 / 岗位启发式 (DEPRECATED) ----------
def _extract_name_position_heuristic(subject: str, orig_filename: str) -> Tuple[str, str]:
    """启发式 (DEPRECATED): 仅在 --no-llm 模式作为兜底使用。

    v2.1 起 LLM 成为默认识别方式 — 对非典型主题/英文姓名失效率高。
    保留函数避免外部 import 挂掉; 真实逻辑在 process_attachment 走 _extract_with_llm。
    """
    text = " ".join([subject or "", orig_filename or ""])
    position = "未填"
    for kw in POSITION_KEYWORDS:
        if kw in text:
            position = kw
            break
    name = "未知"
    for m in NAME_HINT_RE.findall(text):
        if any(kw in m for kw in POSITION_KEYWORDS):
            continue
        if any(sw in m for sw in NAME_STOPWORDS):
            continue
        if len(m) > 3:
            continue
        name = m
        break
    return name, position


def _extract_name_position(subject: str, orig_filename: str) -> Tuple[str, str]:
    """DEPRECATED 兼容 shim — 不再使用, 真实逻辑走 LLM。"""
    return "未知", "未填"


def _extract_email(sender: str) -> str:
    """从邮件 From 头里抽干净的小写邮箱地址。

    输入: '"张三" <zhangsan@hr-tech.com>' 或 'zhangsan@hr-tech.com' 或 '张三 <zhangsan@hr-tech.com>'
    输出: 'zhangsan@hr-tech.com' 抽不到 → 'unknown'
    """
    import re as _re
    if not sender:
        return "unknown"
    m = _re.search(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", sender)
    return (m.group(0).lower() if m else "unknown")


def _extract_resume_text(raw_bytes: bytes, ext: str, *, max_chars: int = 2000) -> Tuple[str, str]:
    """只从简历文件本身抽纯文本。返回 (text, err)；成功时 err=''。

    - .pdf  → pdfminer
    - .docx → python-docx
    不读邮件主题 / 正文 / 附件名。
    默认截断到 2000 字：姓名/求职意向几乎总在文首，过长易导致 LLM JSON 截断。
    """
    ext = (ext or "").lower()
    if not raw_bytes:
        return "", "empty-bytes"
    try:
        if ext == ".pdf":
            from pdfminer.high_level import extract_text as _pdf_extract
            text = _pdf_extract(io.BytesIO(raw_bytes)) or ""
        elif ext == ".docx":
            from docx import Document
            doc = Document(io.BytesIO(raw_bytes))
            parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
            # 表格里常有「姓名 / 求职意向」
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        t = (cell.text or "").strip()
                        if t:
                            parts.append(t)
            text = "\n".join(parts)
        else:
            return "", f"unsupported-ext:{ext}"
    except Exception as e:
        return "", f"extract-error: {type(e).__name__}: {e}"

    # 清零宽/控制字符，压空白
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return "", "empty-text"
    if len(text) > max_chars:
        text = text[:max_chars]
    return text, ""


def _resolve_name_position(
    resume_text: str,
    llm_cfg: Optional["LLMConfig"],
    *,
    content_sha256: str = "",
    llm_cache: Optional[dict] = None,
    fallback_hint: str = "",
) -> Tuple[str, str, bool, bool, str]:
    """统一识别姓名 + 岗位 —— **仅基于简历文件正文**。

    策略:
      1. 若 llm_cfg.enabled (默认): 走 LLM, 抽不到 → ('未知', '未填')
         cache key = 文件内容 sha256；**仅缓存成功结果**，失败不写 cache
      2. 若 --no-llm: 对正文做启发式 (fallback_hint 仅作离线兜底辅助)

    返回: (name, position, name_used_llm, position_used_llm, method)
      method ∈ {'llm', 'llm-cached', 'heuristic', 'no-text'}
    """
    if not (resume_text or "").strip():
        return "未知", "未填", False, False, "no-text"

    if llm_cfg and llm_cfg.enabled:
        cache_key = content_sha256 or hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
        if llm_cache is not None and cache_key in llm_cache:
            cached = llm_cache[cache_key]
            return (cached[0] or "未知", cached[1] or "未填",
                    bool(cached[0]), bool(cached[1]), "llm-cached")

        llm_name, llm_position, err = _extract_with_llm(
            resume_text,
            model=llm_cfg.model, base_url=llm_cfg.base_url, api_key=llm_cfg.api_key,
            timeout=llm_cfg.timeout,
        )
        name = llm_name or "未知"
        position = llm_position or "未填"
        # 只缓存成功抽出的结果，避免把失败/截断永久钉死
        if llm_cache is not None and (llm_name or llm_position):
            llm_cache[cache_key] = (llm_name, llm_position)
        if llm_name or llm_position:
            print(f"[llm] 姓名={llm_name!r} 岗位={llm_position!r} ({err})", file=sys.stderr)
        else:
            print(f"[llm] 抽不到: {err} → fallback 未知-未填", file=sys.stderr)
        return name, position, bool(llm_name), bool(llm_position), "llm"

    # --no-llm: 启发式只看简历正文 (+ 可选 hint)
    name, position = _extract_name_position_heuristic(resume_text, fallback_hint)
    return name, position, False, False, "heuristic"


# ---------- LLM 兜底 ----------
def _extract_with_llm(resume_text: str,
                      *,
                      model: str, base_url: str, api_key: str,
                      timeout: float = 8.0) -> Tuple[Optional[str], Optional[str], str]:
    """调 LLM 从**简历正文**抽 (姓名, 岗位)。失败 → (None, None, error_msg)。

    不接收邮件主题 / 正文 / 附件名。OpenAI 兼容协议。
    """
    import urllib.request
    import urllib.error
    import ssl

    text_trim = (resume_text or "").strip()[:2000]
    if not text_trim:
        return None, None, "empty-resume-text"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content":
             "你是一个中文简历解析助手。用户只提供「简历文件正文」，不要参考任何邮件信息。"
             "从正文抽出 (name, position) 两个字段。仅输出 JSON, 格式: "
             "{\"name\": \"张三\", \"position\": \"后端开发\"}"
             "。name=候选人真实中文姓名（2-4字，优先「姓名：」字段）；"
             "position=求职意向/目标岗位的简短称谓（≤10字，不要带'岗'后缀；"
             "若有多个岗位取第一个，如「后端技术专家 / 架构师」→「后端技术专家」）。"
             "抽不出填空字符串。禁止输出其它文字。"},
            {"role": "user", "content": f"简历正文:\n{text_trim}"},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=req_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return None, None, f"http-error: {type(e).__name__}: {e}"

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        # 有些模型会包 ```json ... ```
        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            obj = json.loads(content)
        else:
            obj = content
        name = (obj.get("name") or "").strip()
        position = (obj.get("position") or "").strip()
        # 二次过滤：name 不能含岗位关键词/停用词；position 不能是投递用语
        if name and (any(kw in name for kw in POSITION_KEYWORDS) or any(sw in name for sw in NAME_STOPWORDS)):
            name = ""
        if position and any(kw in position for kw in ("简历", "投送", "投递", "附件")):
            position = ""
        # 岗位过长截断到首段
        if position and ("/" in position or "／" in position):
            position = re.split(r"[/／]", position)[0].strip()
        if len(position) > 16:
            position = position[:16]
        return (name or None), (position or None), "ok"
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return None, None, f"parse-error: {type(e).__name__}: {e}"


def _safe_save_name(name: str) -> str:
    """Linux 文件名 + Windows 保留字 + 长度。"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\x00", "", name)
    name = name.strip().rstrip(". ")
    return name[:240] or "未命名"


def _person_name_from_saved(filename: str) -> str:
    """从落盘文件名尽量抽出姓名（兼容新旧两种命名）。

    新格式：姓名-岗位.ext → 取首段
    旧格式：resume-tech-01-张磊-后端开发.ext → 无法只靠首段，返回空，交给段匹配
    """
    stem = Path(filename).stem
    if "-" not in stem:
        return stem
    first = stem.split("-", 1)[0]
    # 旧样本名前缀 resume / 纯数字编号 不是姓名
    if first in {"resume", "Resume", "RESUME"} or first.isdigit():
        return ""
    return first


def _filename_has_person_name(filename: str, person_name: str) -> bool:
    """判断落盘文件名是否已包含该姓名。

    兼容：
      - 新：张磊-后端技术专家.pdf
      - 旧：resume-tech-01-张磊-后端开发.pdf
      - 带 uuid：resume-product-02-林婉清-数据产品经理---uuid.docx
    规则：按 '-' 切段后任一段与姓名完全相等；或新格式以「姓名-」开头。
    """
    want = (person_name or "").strip()
    if not want:
        return False
    stem = Path(filename).stem
    if stem == want or stem.startswith(want + "-"):
        return True
    parts = [p for p in stem.split("-") if p]
    return want in parts


def _existing_by_person_name(inbox_dir: Path, person_name: str) -> Optional[str]:
    """若 inbox 已有同姓名落盘文件，返回已有文件名；否则 None。

    忽略隐藏文件（如 .fetched-mail.jsonl）。
    """
    if not person_name:
        return None
    if not inbox_dir.exists():
        return None
    for p in inbox_dir.iterdir():
        if not p.is_file() or p.name.startswith("."):
            continue
        if _filename_has_person_name(p.name, person_name):
            return p.name
    return None


# ---------- 主处理入口 ----------
def process_attachment(
    att: MailAttachment,
    *,
    subject: str = "",
    body: str = "",
    mail_uid: str = "",
    inbox_dir: Path,
    max_file_mb: int,
    max_archive_mb: int,
    max_files_in_archive: int,
    max_ratio: int,
    llm_cfg: Optional["LLMConfig"] = None,
    llm_cache: Optional[dict] = None,
) -> Tuple[List[SavedFile], List[SkippedFile]]:
    """处理一封邮件附件：返回 (落盘列表, 跳过列表)。

    姓名/岗位 **只从简历文件正文** 识别 (PDF/DOCX 抽文本 → LLM)，
    subject/body/mail_uid 保留仅为兼容旧调用签名，不再参与命名。
    落盘名固定为「姓名-岗位.ext」；若 inbox 已有同姓名文件则跳过（不覆盖）。
    llm_cache: 跨附件共享, key=文件内容 sha256
    """
    del subject, body, mail_uid  # 显式丢弃, 避免误用邮件元数据命名
    saved: List[SavedFile] = []
    skipped: List[SkippedFile] = []
    fname = att.filename or "attachment"
    ext = _ext(fname)
    size = len(att.raw_bytes)

    # 1) 后缀白名单
    if ext not in ALLOWED_EXTS:
        skipped.append(SkippedFile(orig_name=fname, reason=f"ext-not-allowed ({ext or 'none'})", size=size))
        return saved, skipped

    # 2) 大小门限
    if size > max_file_mb * 1024 * 1024:
        skipped.append(SkippedFile(orig_name=fname, reason=f"too-large ({size} > {max_file_mb} MB)", size=size))
        return saved, skipped

    # 3) Magic Number 二次校验
    head = att.raw_bytes[:8]
    if not _magic_matches(ext, head):
        skipped.append(SkippedFile(orig_name=fname, reason=f"magic-mismatch (ext={ext}, head={head!r})", size=size))
        return saved, skipped

    # 4) 直接 PDF/DOCX：抽正文 → LLM → 「姓名-岗位.ext」；同姓名已存在则跳过
    if ext in RESUME_EXTS:
        resume_text, texterr = _extract_resume_text(att.raw_bytes, ext)
        if texterr:
            print(f"[extract-text] {fname!r} → {texterr}", file=sys.stderr)
        name, position, _, _, method = _resolve_name_position(
            resume_text, llm_cfg,
            content_sha256=att.sha256_hex(),
            llm_cache=llm_cache,
        )
        print(f"[extract] {fname!r} → 姓名={name!r} 岗位={position!r} via {method} (from-file)",
              file=sys.stderr)
        existed = _existing_by_person_name(inbox_dir, name)
        if existed:
            print(f"[skip-dup-name] {fname!r} 姓名={name!r} 已存在 {existed!r}, 跳过落盘",
                  file=sys.stderr)
            skipped.append(SkippedFile(
                orig_name=fname, size=size,
                reason=f"name-already-exists ({name} -> {existed})",
            ))
            return saved, skipped
        alias = _safe_save_name(f"{name}-{position}{ext}")
        target = inbox_dir / alias
        target.write_bytes(att.raw_bytes)
        saved.append(SavedFile(
            saved_name=target.name, source="direct", orig_name=fname, size=size, sha256=att.sha256_hex(),
            reason=f"whitelist direct save with name-position rename [via {method}|file-text]",
        ))
        return saved, skipped

    # 5) ZIP/RAR：解压后对每个内层 pdf/docx 单独抽正文 → LLM
    try:
        if ext == ".zip":
            inner = _safe_extract_zip(att.raw_bytes,
                                       max_total_mb=max_archive_mb,
                                       max_files=max_files_in_archive,
                                       max_ratio=max_ratio)
        elif ext == ".rar":
            inner = _safe_extract_rar(att.raw_bytes,
                                       max_total_mb=max_archive_mb,
                                       max_files=max_files_in_archive,
                                       max_ratio=max_ratio)
        else:
            inner = []
    except ValueError as e:
        skipped.append(SkippedFile(orig_name=fname, reason=f"archive-rejected ({e})", size=size))
        return saved, skipped

    inner_resume_count = 0
    inner_resume_skipped = 0
    for inner_name, data in inner:
        inner_ext = _ext(inner_name)
        if inner_ext not in RESUME_EXTS:
            inner_resume_skipped += 1
            continue
        if not _magic_matches(inner_ext, data[:8]):
            skipped.append(SkippedFile(
                orig_name=f"{fname}::{inner_name}",
                reason=f"inner-magic-mismatch (ext={inner_ext})",
                size=len(data),
            ))
            continue
        resume_text, texterr = _extract_resume_text(data, inner_ext)
        if texterr:
            print(f"[extract-text] {fname}::{inner_name!r} → {texterr}", file=sys.stderr)
        inner_sha = hashlib.sha256(data).hexdigest()
        inner_name_resolved, inner_position_resolved, _, _, inner_method = _resolve_name_position(
            resume_text, llm_cfg,
            content_sha256=inner_sha,
            llm_cache=llm_cache,
        )
        print(f"[extract] {fname}::{inner_name!r} → 姓名={inner_name_resolved!r} "
              f"岗位={inner_position_resolved!r} via {inner_method} (from-file)",
              file=sys.stderr)
        existed = _existing_by_person_name(inbox_dir, inner_name_resolved)
        if existed:
            print(f"[skip-dup-name] {fname}::{inner_name!r} 姓名={inner_name_resolved!r} "
                  f"已存在 {existed!r}, 跳过落盘", file=sys.stderr)
            skipped.append(SkippedFile(
                orig_name=f"{fname}::{inner_name}", size=len(data),
                reason=f"name-already-exists ({inner_name_resolved} -> {existed})",
            ))
            continue
        inner_alias = _safe_save_name(
            f"{inner_name_resolved}-{inner_position_resolved}{inner_ext}"
        )
        target = inbox_dir / inner_alias
        target.write_bytes(data)
        saved.append(SavedFile(
            saved_name=target.name, source=ext.lstrip("."), orig_name=f"{fname}::{inner_name}",
            size=len(data), sha256=inner_sha,
            reason=f"extracted from {fname} [via {inner_method}|file-text]",
        ))
        inner_resume_count += 1

    if inner_resume_count == 0 and not skipped:
        skipped.append(SkippedFile(
            orig_name=fname, size=size,
            reason=f"archive-opened-but-no-resume (skipped_inner={inner_resume_skipped})",
        ))
    return saved, skipped


# ============================================================
# LLM 兜底配置
# ============================================================
@dataclass
class LLMConfig:
    enabled: bool = False
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    timeout: float = 8.0


def llm_config_from_env(args) -> LLMConfig:
    """从 CLI + env 拼 LLMConfig (v2.1 默认启用)。

    --no-llm → 关
    默认开 → 从 DEEPSEEK_API_KEY / FETCH_LLM_API_KEY / --llm-api-key 取 key
    """
    if args.no_llm:
        return LLMConfig(enabled=False)
    api_key = (args.llm_api_key
               or os.environ.get("FETCH_LLM_API_KEY", "")
               or os.environ.get("DEEPSEEK_API_KEY", ""))
    return LLMConfig(
        enabled=True,
        model=args.llm_model,
        base_url=args.llm_base_url,
        api_key=api_key,
        timeout=args.llm_timeout,
    )


# ============================================================
# 主流程
# ============================================================
def write_fetched_mail_log(inbox_dir: Path, records: List[dict]) -> Path:
    log_path = inbox_dir / ".fetched-mail.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return log_path


def backend_from_args(args) -> MailBackend:
    if args.backend == "mock":
        mb = Path(args.mailbox_dir).resolve()
        return MockMailBackend(mb)
    return LiveImapBackend(
        host=args.imap_host, port=args.imap_port,
        user=args.imap_user, password=args.imap_pass, ssl=not args.no_ssl,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="收件箱 → 仅保留 PDF/DOCX 简历到 inbox（ZIP/RAR 自动解压）")
    parser.add_argument("--backend", choices=["mock", "live"], default=os.environ.get("MAIL_BACKEND", "mock"))
    parser.add_argument("--inbox-dir", default=os.environ.get("HR_INBOX_DIR", "./inbox"))
    parser.add_argument("--folder", default=os.environ.get("MAIL_FOLDER", "INBOX"))
    parser.add_argument("--since", default=None,
                        help="只拉该日期之后的邮件 (YYYY-MM-DD)。默认见 --days-ago")
    parser.add_argument("--days-ago", type=int, default=int(os.environ.get("FETCH_DAYS_AGO", "2")),
                        help="默认拉今天往前 N 天的邮件 (默认 2)。--since 显式传则覆盖此值")
    parser.add_argument("--max", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true",
                        help="列出将拉下来的邮件/附件，不真写盘")

    # mock 专用
    parser.add_argument("--mailbox-dir", default="./mailbox")

    # live 专用
    parser.add_argument("--imap-host", default=os.environ.get("IMAP_HOST", "imap.qq.com"))
    parser.add_argument("--imap-port", type=int, default=int(os.environ.get("IMAP_PORT", "993")))
    parser.add_argument("--imap-user", default=os.environ.get("IMAP_USER", ""))
    parser.add_argument("--imap-pass", default=os.environ.get("IMAP_PASS", ""))
    parser.add_argument("--no-ssl", action="store_true")

    # 安全门限
    parser.add_argument("--max-file-mb", type=int, default=50, help="单附件大小上限 (MB)")
    parser.add_argument("--max-archive-mb", type=int, default=200, help="单压缩包解压后总大小上限 (MB)")
    parser.add_argument("--max-files-in-archive", type=int, default=1000, help="单压缩包成员数上限")
    parser.add_argument("--max-ratio", type=int, default=100, help="解压比上限 (zip bomb 防护)")

    # LLM 识别 (v2.1+ 默认启用, 不再依赖启发式)
    parser.add_argument("--no-llm", action="store_true",
                        help="关闭 LLM 识别, 改用启发式 (不推荐, 仅离线/排错用)")
    parser.add_argument("--llm-model", default=os.environ.get("FETCH_LLM_MODEL", "deepseek-v4-flash"))
    parser.add_argument("--llm-base-url", default=os.environ.get("FETCH_LLM_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--llm-api-key", default=os.environ.get("FETCH_LLM_API_KEY", ""))
    parser.add_argument("--llm-timeout", type=float, default=float(os.environ.get("FETCH_LLM_TIMEOUT", "8")),
                        help="单次 LLM 调用超时 (秒)")

    args = parser.parse_args()

    inbox_dir = Path(args.inbox_dir).resolve()
    inbox_dir.mkdir(parents=True, exist_ok=True)

    # 时间窗口: --since 显式传优先, 否则按 --days-ago (默认 2 天) 算
    if args.since:
        since_str = args.since
    else:
        since_date = (datetime.now() - timedelta(days=args.days_ago)).date()
        since_str = since_date.isoformat()
    print(f"[fetch] 时间窗口: since={since_str} (未读 + seen=False; --since 可覆盖 --days-ago={args.days_ago})",
          file=sys.stderr)

    backend = backend_from_args(args)
    print(f"[fetch] backend={backend.name} folder={args.folder} inbox_dir={inbox_dir}", file=sys.stderr)
    if backend.name == "live" and (not args.imap_user or not args.imap_pass):
        print("[fetch] live 后端必须 --imap-user + --imap-pass(或 env)", file=sys.stderr)
        return 2

    llm_cfg = llm_config_from_env(args)
    if llm_cfg.enabled:
        if not llm_cfg.api_key:
            print("[fetch] LLM 默认启用但缺 api key (FETCH_LLM_API_KEY / DEEPSEEK_API_KEY / --llm-api-key)。"
                  "如需离线跑, 加 --no-llm 改用启发式。", file=sys.stderr)
            return 2
        print(f"[fetch] LLM 识别启用  model={llm_cfg.model}  timeout={llm_cfg.timeout}s",
              file=sys.stderr)
    else:
        print(f"[fetch] LLM 关闭 (--no-llm), 改用启发式 (不推荐)", file=sys.stderr)

    llm_cache: dict = {}  # 跨附件共享, 避免同 (subj+filename+body-hash) 重复调 LLM
    pulled_records: List[dict] = []
    n_mail = 0
    n_saved = 0
    n_skipped = 0
    started = time.time()

    for msg in backend.list_messages(args.folder, since=since_str):
        n_mail += 1
        if n_mail > args.max:
            print(f"[fetch] 触达 --max={args.max}, 停止", file=sys.stderr)
            break

        mail_record = {
            "uid": msg.uid, "subject": msg.subject, "sender": msg.sender, "date": msg.date,
            "saved_files": [], "skipped_files": [],
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        for att in msg.attachments:
            if args.dry_run:
                # dry-run: 报告预期结果但不写盘
                ext = _ext(att.filename or "")
                head = (att.raw_bytes or b"")[:8]
                ok = ext in ALLOWED_EXTS and _magic_matches(ext, head)
                mail_record["saved_files"].append({
                    "orig_name": att.filename, "ext": ext, "magic_ok": bool(ok),
                    "size": len(att.raw_bytes),
                    "sha256": att.sha256_hex(),
                })
                continue

            saved_list, skipped_list = process_attachment(
                att, subject=msg.subject, body=msg.body, mail_uid=msg.uid,
                inbox_dir=inbox_dir,
                max_file_mb=args.max_file_mb, max_archive_mb=args.max_archive_mb,
                max_files_in_archive=args.max_files_in_archive, max_ratio=args.max_ratio,
                llm_cfg=llm_cfg, llm_cache=llm_cache,
            )
            for s in saved_list:
                n_saved += 1
                mail_record["saved_files"].append(dataclasses.asdict(s))
            for s in skipped_list:
                n_skipped += 1
                mail_record["skipped_files"].append(dataclasses.asdict(s))

        pulled_records.append(mail_record)
        n_this = len(mail_record["saved_files"])
        s_this = len(mail_record["skipped_files"])
        print(f"[fetch] #{n_mail:03d} {msg.sender} | {msg.subject!r} | saved={n_this} skipped={s_this}",
              file=sys.stderr)

    if args.dry_run:
        summary = {
            "backend": backend.name, "mails_seen": n_mail,
            "records": pulled_records,
            "elapsed_sec": round(time.time() - started, 3),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if not pulled_records:
        print(f"[fetch] 没有拉到任何邮件（folder={args.folder} since={since_str}）", file=sys.stderr)
        return 0

    log_path = write_fetched_mail_log(inbox_dir, pulled_records)
    print(f"[fetch] 落盘 {n_saved} 份简历 / 跳过 {n_skipped} 个附件 / log={log_path.name}",
          file=sys.stderr)
    print(f"[fetch] 总耗时 {time.time() - started:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())