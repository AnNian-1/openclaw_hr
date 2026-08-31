#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""夹具过滤 + JD 截断（不调 embedding API）。"""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("search_talent_pool", HERE / "search_talent_pool.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["search_talent_pool"] = mod
spec.loader.exec_module(mod)


def test_fixture_name():
    assert mod.is_fixture_candidate({"name": "夹具近邻", "parsed": {}})
    assert mod.is_fixture_candidate({
        "name": "张三",
        "parsed": {"self_evaluation": "测试夹具，非真实候选人。"},
    })
    assert not mod.is_fixture_candidate({
        "name": "张磊",
        "parsed": {"self_evaluation": "交易中台后端。"},
        "full_text": "姓名:张磊",
    })


def test_jd_truncate(monkey_limit=None):
    long_jd = "后端" * 800
    text = mod.prepare_jd_text(long_jd)
    assert len(text) <= mod.jd_embed_max_chars()
    assert len(text) < len(long_jd)


if __name__ == "__main__":
    test_fixture_name()
    test_jd_truncate()
    print("ok")
