# 入职夹具备份（非运行时真源）

**真源**在工作区，不在这里：

| 真源 | 路径 |
|------|------|
| 入职工作流落盘 | `workspace-onboarding/stub-state/`（现为 `yuangong1`） |
| 跟进总表 | `workspace-onboarding/review-state/reviews.json` |
| 花名册 | `hcm/hcm.db` |

本目录只是上述内容的一份 **QA 备份**。测试节点空库可用 `HCM_SEED_FIXTURES=1 python seed.py` 灌员工1。主节点不要跑这条：花名册已经有人，默认 `python seed.py` 读的是工作区 `stub-state/`。

当前只留 `onboarding-stub-state/yuangong1`。员工2 原入职完成态已撤，该显示名留给新简历。
