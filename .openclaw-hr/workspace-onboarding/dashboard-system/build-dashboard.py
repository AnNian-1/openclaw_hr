#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【已停用】旧入职看板生成器。Canvas 入职进度看板请用：
  workspace-onboarding/skills/generating-onboarding-dashboard/scripts/build-dashboard.sh

本文件不要再跑：它从 stub-state 拼准备节点，并总会画出 4 个 review 格
（已与现行产品不符：准备节点读 HCM；未开通跟进不画空节点）。
"""
import sys

print(
    "[dashboard] 请改用 skills/generating-onboarding-dashboard/scripts/build-dashboard.sh",
    file=sys.stderr,
)
sys.exit(2)
