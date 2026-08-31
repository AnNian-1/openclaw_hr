#!/usr/bin/env python3
"""ingest 清理不得删聚合产物。"""
import tempfile
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ingest_archive", HERE / "ingest_archive.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "manager.json").write_text("{}", encoding="utf-8")
        (d / "aggregated-data.json").write_text('{"keep": true}', encoding="utf-8")
        (d / "aggregated-report.md").write_text("# x", encoding="utf-8")
        (d / "report.html").write_text("<html></html>", encoding="utf-8")
        (d / "old.docx").write_bytes(b"PK")
        mod.clear_subject_dir(d)
        assert not (d / "manager.json").exists()
        assert not (d / "old.docx").exists()
        assert (d / "aggregated-data.json").exists()
        assert (d / "aggregated-report.md").exists()
        assert (d / "report.html").exists()
    print("ok")


if __name__ == "__main__":
    main()
