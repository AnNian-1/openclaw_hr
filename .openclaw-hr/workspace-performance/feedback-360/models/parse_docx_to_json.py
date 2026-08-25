#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口：转发到 Skill 内正式脚本 docx_to_json.py

正式解析逻辑在：
  skills/aggregating-360-feedback/scripts/docx_to_json.py
摄入压缩包请用：
  skills/aggregating-360-feedback/scripts/ingest_archive.py
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SKILL_DOCX = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "aggregating-360-feedback"
    / "scripts"
    / "docx_to_json.py"
)

if not SKILL_DOCX.is_file():
    sys.exit(f"找不到正式脚本: {SKILL_DOCX}")

# 无参时默认解析 source_feedback 下已有人员目录需显式传入；
# 这里保持「传目录」语义，直接 exec 正式脚本。
sys.argv[0] = str(SKILL_DOCX)
runpy.run_path(str(SKILL_DOCX), run_name="__main__")
