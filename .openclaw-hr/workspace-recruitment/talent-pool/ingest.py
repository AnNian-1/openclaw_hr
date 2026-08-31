#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility wrapper. Canonical ingest lives in the Skill scripts dir.

Do not keep a second copy here: the old file hardcoded ~/.openclaw-hr and
DashScope text-embedding-v3, which drifted from SiliconFlow Qwen3.
"""
import os
import sys
from pathlib import Path

_target = (
    Path(__file__).resolve().parent.parent
    / "skills/ingesting-talent-pool/scripts/ingest_talent_pool.py"
)
os.execv(sys.executable, [sys.executable, str(_target), *sys.argv[1:]])
