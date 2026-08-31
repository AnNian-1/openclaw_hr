#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ingest_archive.py — 从 zip/rar 摄入 360 反馈 Word 表并生成 JSON

约定：
  - 压缩包文件名**不固定**（任意 .zip / .rar 均可）
  - 所有落盘资料统一在 feedback-360/source_feedback/ 下
  - 子目录名由 DOCX 内「被评估人」字段决定，不依赖压缩包名
    例：表内被评估人=员工1 → source_feedback/yuangong1/

流程：
  1. 定位压缩包（显式路径，或扫描 source_feedback/ 顶层）
  2. 解压到临时目录，读首份 DOCX 得到 subject → 决定 out_dir
  3. 拷贝 DOCX + 解析 JSON 到 source_feedback/<subject_slug>/
  4. 后续 check_feedback / aggregate 读该 JSON 目录

CLI：
  python3 ingest_archive.py                         # 自动找 source_feedback 顶层唯一压缩包
  python3 ingest_archive.py <archive.zip|rar>        # 指定任意文件名的包
  python3 ingest_archive.py <archive> <out_dir>      # 可选：强制输出目录（仍建议在 source_feedback 下）

退出码：0 成功；1 数据/解析问题；2 用法错误
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from docx_to_json import (  # noqa: E402
    convert_dir,
    parse_docx,
    subject_dir_name,
)


def _require_deps():
    missing = []
    try:
        import docx  # noqa: F401
    except ImportError:
        missing.append("python-docx")
    try:
        import pypinyin  # noqa: F401
    except ImportError:
        missing.append("pypinyin")
    if missing:
        die(
            "缺少 Python 依赖："
            + "、".join(missing)
            + "。请在 openclaw-hr 环境执行：pip install -r "
            + str(SCRIPTS.parent / "requirements.txt"),
            2,
        )


# workspace-performance/feedback-360
FEEDBACK_360 = Path(__file__).resolve().parents[3] / "feedback-360"
SOURCE_FEEDBACK = FEEDBACK_360 / "source_feedback"

ARCHIVE_SUFFIXES = {".zip", ".rar", ".r00"}


def die(msg: str, code: int = 1):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def list_top_archives(dir_path: Path) -> list[Path]:
    """只扫 source_feedback 顶层压缩包，不进各人员子目录。"""
    if not dir_path.is_dir():
        return []
    found = []
    for p in sorted(dir_path.iterdir()):
        if p.is_file() and p.suffix.lower() in ARCHIVE_SUFFIXES and not p.name.startswith("."):
            found.append(p)
    return found


def resolve_archive(arg: str | None) -> Path:
    if arg:
        archive = Path(arg).expanduser().resolve()
        if not archive.is_file():
            die(f"压缩包不存在: {archive}", 2)
        if archive.suffix.lower() not in ARCHIVE_SUFFIXES:
            die(f"不支持的压缩格式: {archive.suffix}（仅 .zip / .rar）", 2)
        return archive

    SOURCE_FEEDBACK.mkdir(parents=True, exist_ok=True)
    archives = list_top_archives(SOURCE_FEEDBACK)
    if not archives:
        die(
            f"未指定压缩包，且 {SOURCE_FEEDBACK} 顶层没有 .zip/.rar。\n"
            f"请把反馈压缩包放到该目录后重试，或显式传入路径。",
            2,
        )
    if len(archives) > 1:
        names = "\n  - ".join(p.name for p in archives)
        die(
            f"{SOURCE_FEEDBACK} 顶层有多份压缩包，请显式指定一份：\n  - {names}",
            2,
        )
    return archives[0].resolve()


def extract_to_temp(archive: Path, tmp_path: Path) -> list[Path]:
    suffix = archive.suffix.lower()
    if suffix == ".zip":
        _extract_zip(archive, tmp_path)
    elif suffix in (".rar", ".r00"):
        _extract_rar(archive, tmp_path)
    else:
        die(f"不支持的压缩格式: {archive.suffix}", 2)

    docx_files = sorted(
        p for p in tmp_path.rglob("*.docx")
        if not p.name.startswith("~$") and not p.name.startswith(".")
    )
    if not docx_files:
        die(f"压缩包内未找到 .docx：{archive}")
    return docx_files


def _extract_zip(archive: Path, dest: Path):
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                name = info.filename
                if info.flag_bits & 0x800 == 0:
                    try:
                        name = name.encode("cp437").decode("gbk")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass
                out = dest / name
                if not str(out.resolve()).startswith(str(dest.resolve())):
                    die(f"非法压缩路径（zip-slip）: {info.filename}")
                if info.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                else:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as e:
        die(f"无法打开 zip：{e}")


def _extract_rar(archive: Path, dest: Path):
    try:
        import rarfile
    except ImportError:
        die("解析 .rar 需要安装 rarfile：pip install rarfile（并需系统 unrar）")
    try:
        with rarfile.RarFile(archive) as rf:
            rf.extractall(dest)
    except rarfile.Error as e:
        die(f"无法打开 rar：{e}")


def peek_subject(docx_files: list[Path]) -> str:
    """从首份可解析 DOCX 读取被评估人；不依赖压缩包文件名。"""
    errors = []
    for path in docx_files:
        try:
            row = parse_docx(path)
            subject = (row.get("subject") or "").strip()
            if subject:
                return subject
            errors.append(f"{path.name}: 被评估人为空")
        except Exception as e:
            errors.append(f"{path.name}: {e}")
    detail = "; ".join(errors[:3]) if errors else "无"
    die(f"无法从 DOCX 读取被评估人（不依赖压缩包名）。详情：{detail}")


def resolve_out_dir(subject: str, explicit: Path | None) -> Path:
    """落盘目录：默认 source_feedback/<subject_slug>/，与压缩包名无关。"""
    if explicit is not None:
        out = explicit
        # 提醒：强制目录也应落在 source_feedback 下
        try:
            out.resolve().relative_to(SOURCE_FEEDBACK.resolve())
        except ValueError:
            print(
                f"⚠️ 输出目录不在 {SOURCE_FEEDBACK} 下：{out}\n"
                f"   建议统一落盘到 source_feedback/<被评估人>/",
                file=sys.stderr,
            )
        return out
    SOURCE_FEEDBACK.mkdir(parents=True, exist_ok=True)
    return SOURCE_FEEDBACK / subject_dir_name(subject)


KEEP_FILES = {"aggregated-data.json", "aggregated-report.md", "report.html"}


def clear_subject_dir(out_dir: Path):
    """清空人员目录内旧源数据 DOCX/JSON，保留聚合产物。"""
    if not out_dir.exists():
        return
    for p in out_dir.iterdir():
        if p.name.startswith(".") or p.name in KEEP_FILES:
            continue
        if p.name.startswith("aggregated-"):
            continue
        if p.suffix.lower() in {".docx", ".json"} and p.is_file():
            p.unlink()


def copy_docx(docx_files: list[Path], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in docx_files:
        target = out_dir / src.name
        shutil.copy2(src, target)
        copied.append(target)
    return copied


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    _require_deps()
    # 用法：[] | [archive] | [archive out_dir]
    archive_arg = argv[0] if len(argv) >= 1 else None
    explicit_out = Path(argv[1]).expanduser().resolve() if len(argv) >= 2 else None
    if len(argv) > 2:
        print(
            "用法: python3 ingest_archive.py [archive.zip|rar] [out_dir]",
            file=sys.stderr,
        )
        sys.exit(2)

    archive = resolve_archive(archive_arg)
    print(f"📦 压缩包：{archive.name}（文件名不参与落盘命名）")
    print(f"   路径：{archive}")

    with tempfile.TemporaryDirectory(prefix="360-ingest-") as tmp:
        tmp_path = Path(tmp)
        docx_in_tmp = extract_to_temp(archive, tmp_path)
        print(f"   解压出 {len(docx_in_tmp)} 份 DOCX")

        subject = peek_subject(docx_in_tmp)
        out_dir = resolve_out_dir(subject, explicit_out)
        print(f"👤 被评估人：{subject}")
        print(f"📁 落盘目录：{out_dir}")

        out_dir.mkdir(parents=True, exist_ok=True)
        clear_subject_dir(out_dir)
        copied = copy_docx(docx_in_tmp, out_dir)

    print("📝 解析 DOCX → JSON")
    try:
        written = convert_dir(out_dir, out_dir)
    except Exception as e:
        die(f"DOCX 解析失败: {e}")

    print(f"\n✅ 摄入完成：{len(copied)} DOCX + {len(written)} JSON → {out_dir}")
    print("   下一步：")
    print(f"   python3 check_feedback.py {out_dir}")
    print(f"   python3 aggregate.py {out_dir}")
    print(f"   → 聚合数据写出：{out_dir / 'aggregated-data.json'}")
    print(f"   → 综合分析报告约定写到：{out_dir / 'aggregated-report.md'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
