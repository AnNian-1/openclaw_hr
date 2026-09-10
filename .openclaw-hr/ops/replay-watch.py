#!/usr/bin/env python3
"""主节点复跑监测：对照基线扫日记 / MEMORY.md / 做梦报告 / sqlite / 会话 / SSH。

不改任何记忆文件。输出 JSON 到 stdout；--write 同时落盘 latest。
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROFILE = Path(os.environ.get("OPENCLAW_STATE_DIR", "/opt/openclaw-hr/.openclaw-hr"))
OPS = PROFILE / "ops"
BASELINE_PATH = OPS / "replay-watch-baseline.json"
LATEST_PATH = OPS / "replay-watch-latest.json"
BLOCKLIST = Path("/opt/hr-ops/dream-gate-blocklist.txt")
LOCAL_BLOCKLIST = OPS / "dream-gate-blocklist.local.txt"
SH = timezone(timedelta(hours=8))


def load_terms() -> list[str]:
    terms: list[str] = []
    for p in (BLOCKLIST, LOCAL_BLOCKLIST):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                terms.append(s)
    return terms


def hits(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in text]


def iso_sh(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=SH)
    return dt.strftime("%Y-%m-%d %H:%M:%S %z")


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROFILE))
    except ValueError:
        return str(p)


def diary_files() -> list[Path]:
    out: list[Path] = []
    for ws in sorted(PROFILE.glob("workspace-*")):
        mem = ws / "memory"
        if not mem.is_dir():
            continue
        for p in mem.glob("*.md"):
            if p.is_file():
                out.append(p)
    return out


def memory_md_files() -> list[Path]:
    return sorted(p for p in PROFILE.glob("workspace-*/MEMORY.md") if p.is_file())


def dream_reports() -> list[Path]:
    out: list[Path] = []
    for ws in sorted(PROFILE.glob("workspace-*")):
        d = ws / "memory" / "dreaming"
        if d.is_dir():
            out.extend(sorted(x for x in d.rglob("*.md") if x.is_file()))
    return out


def file_info(p: Path, terms: list[str]) -> dict:
    text = p.read_text(encoding="utf-8", errors="replace")
    st = p.stat()
    return {
        "path": rel(p),
        "bytes": st.st_size,
        "mtime": iso_sh(st.st_mtime),
        "hits": hits(text, terms),
    }


def sqlite_status() -> list[dict]:
    rows: list[dict] = []
    mem = PROFILE / "memory"
    if not mem.is_dir():
        return rows
    for f in sorted(mem.glob("*.sqlite")):
        item = {
            "name": f.name,
            "bytes": f.stat().st_size,
            "mtime": iso_sh(f.stat().st_mtime),
            "files": None,
            "chunks": None,
        }
        try:
            c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
            try:
                item["files"] = c.execute("select count(*) from files").fetchone()[0]
                item["chunks"] = c.execute("select count(*) from chunks").fetchone()[0]
            except sqlite3.Error:
                pass
            c.close()
        except sqlite3.Error:
            pass
        rows.append(item)
    return rows


def session_keys() -> list[dict]:
    out: list[dict] = []
    agents = PROFILE / "agents"
    if not agents.is_dir():
        return out
    for sj in sorted(agents.glob("*/sessions/sessions.json")):
        agent = sj.parts[-3]
        try:
            data = json.loads(sj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key, meta in data.items():
            if not isinstance(meta, dict):
                continue
            out.append(
                {
                    "agent": agent,
                    "key": key,
                    "chatType": meta.get("chatType"),
                    "updatedAt": meta.get("updatedAt"),
                }
            )
    return out


def jsonl_sessions() -> list[dict]:
    out: list[dict] = []
    agents = PROFILE / "agents"
    if not agents.is_dir():
        return out
    for p in sorted(agents.glob("*/sessions/*.jsonl")):
        if p.name.endswith(".trajectory.jsonl"):
            continue
        st = p.stat()
        out.append(
            {
                "path": rel(p),
                "bytes": st.st_size,
                "mtime": iso_sh(st.st_mtime),
            }
        )
    return out


def ssh_status() -> dict:
    notty = 0
    pts = 0
    startups = None
    try:
        raw = subprocess.check_output(["pgrep", "-a", "sshd"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raw = ""
    for line in raw.splitlines():
        if "root@notty" in line:
            notty += 1
        elif "root@" in line and "sshd:" in line:
            pts += 1
        m = re.search(r"(\d+)\s+of\s+10-100\s+startups", line)
        if m:
            startups = int(m.group(1))
    users = []
    try:
        wraw = subprocess.check_output(["who"], text=True, stderr=subprocess.DEVNULL)
        for line in wraw.splitlines():
            if line.strip():
                users.append(line.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return {
        "notty": notty,
        "pts": pts,
        "startups_unauth": startups,
        "who": users,
    }


def services() -> dict:
    paths = {
        "hcm-backend": (8000, "/api/health"),
        "hcm-frontend": (5173, "/"),
        "gateway": (18790, "/health"),
        "canvas": (18999, "/__openclaw__/healthz"),
    }
    out = {}
    for name, (port, path) in paths.items():
        try:
            raw = subprocess.check_output(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "2",
                    f"http://127.0.0.1:{port}{path}",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            code = int(raw.strip() or "0")
        except (subprocess.CalledProcessError, ValueError):
            code = 0
        out[name] = code
    return out


def cron_job() -> dict:
    p = PROFILE / "cron" / "jobs.json"
    if not p.is_file():
        return {"present": False}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"present": True, "parse_error": True}
    jobs = data.get("jobs") or []
    if not jobs:
        return {"present": True, "jobs": 0}
    j = jobs[0]
    sch = j.get("schedule") or {}
    return {
        "present": True,
        "name": j.get("name"),
        "enabled": j.get("enabled"),
        "expr": sch.get("expr"),
        "tz": sch.get("tz"),
    }


def promote_procs() -> list[str]:
    try:
        raw = subprocess.check_output(["ps", "ax", "-o", "args="], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    hits_ = []
    for line in raw.splitlines():
        if "AGENT_LOOP_TICK" in line or "replay-watch" in line:
            continue
        if re.search(r"openclaw\s+memory\s+promote|\bmemory\s+promote\s+--apply\b", line):
            hits_.append(line.strip()[:200])
    return hits_


def snapshot() -> dict:
    terms = load_terms()
    diaries = [file_info(p, terms) for p in diary_files()]
    memories = [file_info(p, terms) for p in memory_md_files()]
    dreams = [file_info(p, terms) for p in dream_reports()]
    sql = sqlite_status()
    keys = session_keys()
    jsonl = jsonl_sessions()
    return {
        "checked_at": iso_sh(),
        "baseline_stamp": "20260903T114546Z",
        "diaries": diaries,
        "memory_md": memories,
        "dream_reports": dreams,
        "sqlite": sql,
        "session_keys": keys,
        "jsonl": jsonl,
        "ssh": ssh_status(),
        "services": services(),
        "cron": cron_job(),
        "promote_procs": promote_procs(),
        "counts": {
            "diaries": len(diaries),
            "memory_md": len(memories),
            "dream_reports": len(dreams),
            "sqlite_files_indexed": sum(x["files"] or 0 for x in sql),
            "sqlite_chunks": sum(x["chunks"] or 0 for x in sql),
            "session_keys": len(keys),
            "jsonl": len(jsonl),
            "diary_hits": sum(1 for d in diaries if d["hits"]),
            "memory_hits": sum(1 for d in memories if d["hits"]),
            "dream_hits": sum(1 for d in dreams if d["hits"]),
        },
    }


def alerts(cur: dict, base: dict | None) -> list[dict]:
    out: list[dict] = []
    c = cur["counts"]

    def add(sev: str, code: str, msg: str) -> None:
        out.append({"sev": sev, "code": code, "msg": msg})

    if c["memory_md"]:
        add("danger", "memory_md", f"出现 {c['memory_md']} 份 MEMORY.md（基线为 0；可能是 23:00 短时 promote）")
    if c["memory_hits"]:
        add("danger", "memory_hits", "MEMORY.md 命中闸关键词，不要推备")
    if c["dream_hits"]:
        add("warning", "dream_hits", "做梦报告命中闸关键词，不要合并")
    if c["diary_hits"]:
        add("warning", "diary_hits", "域日记命中闸关键词，今晚不要当沉淀原料")
    if cur.get("promote_procs"):
        add("danger", "promote", "检测到 memory promote 进程")
    cron = cur.get("cron") or {}
    if cron.get("enabled") is True and cron.get("expr") == "0 23 * * *":
        pass
    elif cron.get("present"):
        add("info", "cron_changed", f"做梦 cron 不是预期：enabled={cron.get('enabled')} expr={cron.get('expr')}")
    for name, code in (cur.get("services") or {}).items():
        if code != 200:
            add("warning", "svc", f"{name} HTTP {code}")

    if base:
        bc = base.get("counts") or {}
        if c["diaries"] > bc.get("diaries", 0):
            add("info", "new_diary", f"新日记 {c['diaries'] - bc.get('diaries', 0)} 份（session-memory 在写，预期）")
        if c["dream_reports"] > bc.get("dream_reports", 0):
            add("info", "new_dream", f"新做梦报告 {c['dream_reports'] - bc.get('dream_reports', 0)} 份")
        if c["session_keys"] > bc.get("session_keys", 0):
            add("info", "new_session", f"新会话 key {c['session_keys'] - bc.get('session_keys', 0)} 个")
        if c["sqlite_files_indexed"] > bc.get("sqlite_files_indexed", 0):
            add("info", "sqlite_index", "sqlite 新索引了日记，检索已能搜到")
        bkeys = {x["key"] for x in base.get("session_keys") or []}
        for sk in cur.get("session_keys") or []:
            if sk["key"] not in bkeys and "feishu" in (sk["key"] or ""):
                add("info", "feishu_session", f"新飞书会话 {sk['key']}")

    ssh = cur.get("ssh") or {}
    if ssh.get("pts"):
        add("info", "ssh_pts", f"交互 SSH {ssh['pts']} 路（who: {'; '.join(ssh.get('who') or [])}）")
    if (ssh.get("startups_unauth") or 0) >= 8:
        add("warning", "ssh_startups", f"未完成 SSH 握手 {ssh['startups_unauth']}（MaxStartups 10 开始丢）")

    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    OPS.mkdir(parents=True, exist_ok=True)
    cur = snapshot()
    base = None
    if BASELINE_PATH.is_file() and not args.write_baseline:
        try:
            base = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            base = None
    cur["alerts"] = alerts(cur, base)
    text = json.dumps(cur, ensure_ascii=False, indent=2)
    if args.write_baseline:
        BASELINE_PATH.write_text(text + "\n", encoding="utf-8")
        cur["wrote_baseline"] = str(BASELINE_PATH)
    if args.write or args.write_baseline:
        LATEST_PATH.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
