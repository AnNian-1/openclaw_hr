#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility wrapper. Canonical search lives in the Skill scripts dir.

The old copy hardcoded DashScope text-embedding-v3 and ~/.openclaw-hr.
"""
import os
import sys
from pathlib import Path

_target = (
    Path(__file__).resolve().parent.parent
    / "skills/searching-talent-pool/scripts/search_talent_pool.py"
)
os.execv(sys.executable, [sys.executable, str(_target), *sys.argv[1:]])
