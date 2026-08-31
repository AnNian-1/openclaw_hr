#!/usr/bin/env python3
"""REC-RAR: _safe_extract_rar 解内层 docx；rar-slip 拒绝。需 conda openclaw-hr PATH 上的 unrar。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ENVBIN = Path.home() / "miniconda3/envs/openclaw-hr/bin"
os.environ["PATH"] = f"{ENVBIN}:{os.environ.get('PATH', '')}"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/fetching-resumes-by-mail/scripts"))
from fetch_resumes import _safe_extract_rar  # noqa: E402

DOCX_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>姓名：夹具RAR测试</w:t></w:r></w:p>
<w:p><w:r><w:t>目标岗位：后端开发工程师</w:t></w:r></w:p></w:body></w:document>""".encode("utf-8")
CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
RELS = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _write_min_docx(path: Path) -> None:
    import zipfile

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/document.xml", DOCX_XML)


def _rar_a(archive: Path, *members: Path, cwd: Path) -> None:
    rar = ENVBIN / "rar"
    cmd = [str(rar), "a", "-ep1", str(archive)]
    cmd.extend(str(m.relative_to(cwd)) if m.is_absolute() else str(m) for m in members)
    subprocess.check_call(cmd, cwd=cwd, stdout=subprocess.DEVNULL)


def main() -> int:
    unrar = ENVBIN / "unrar"
    if not unrar.is_file():
        print("FAIL: unrar missing; run scripts/ensure-rar-tools.sh", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        docx = td_p / "夹具RAR测试-后端.docx"
        _write_min_docx(docx)
        archive = td_p / "resume.rar"
        _rar_a(archive, docx, cwd=td_p)
        inner = _safe_extract_rar(archive.read_bytes(), max_total_mb=20, max_files=50, max_ratio=100)
        names = [n for n, _ in inner]
        if "夹具RAR测试-后端.docx" not in names:
            print(f"FAIL: expected inner docx, got {names}", file=sys.stderr)
            return 1
        body = next(data for n, data in inner if n.endswith(".docx"))
        if "夹具RAR测试".encode("utf-8") not in body:
            print("FAIL: inner docx missing marker text", file=sys.stderr)
            return 1
        print("PASS extract inner docx")

        outside = td_p / "outside.docx"
        _write_min_docx(outside)
        slip2 = td_p / "slip-rel.rar"
        subprocess.check_call(
            [str(ENVBIN / "rar"), "a", "-ap../", str(slip2), "outside.docx"],
            cwd=td_p,
            stdout=subprocess.DEVNULL,
        )
        listing = subprocess.check_output([str(ENVBIN / "unrar"), "lb", str(slip2)], text=True)
        print("slip rar members:", listing.strip())
        try:
            _safe_extract_rar(slip2.read_bytes(), max_total_mb=20, max_files=50, max_ratio=100)
            if ".." in listing:
                print("FAIL: rar-slip was not blocked", file=sys.stderr)
                return 1
            print("WARN: rar stored flattened name; skip slip assert")
        except ValueError as e:
            if "slip" not in str(e).lower() and ".." not in str(e):
                print(f"FAIL: unexpected reject {e}", file=sys.stderr)
                return 1
            print(f"PASS rar-slip blocked: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
