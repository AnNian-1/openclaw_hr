# 公共事实池 · Common Pool

> 本目录为 **`README.md` 「十、公共事实池（Common Pool）」** 一章在磁盘上的落点。
>
> **当前课程交付尚未启用此池的写入/读取流程。** 本目录现为骨架，正式目录落地后，各业务子 Agent 应通过 Skill 在此消费事实。

## 目录约定

```
common/
├── README.md                       # 本文件
├── people/                         # 唯一身份记录（按 person_id 命名）
│   └── person-<person_id>.json
├── archive/                        # 已不再是"候选人"的人员档案（入职完成后迁入）
│   └── <姓名或 person_id>/
│       ├── resume.md               # 原始简历副本
│       ├── parsed.json             # 解析产出
│       ├── scoring.json            # 评分产出
│       └── interview/              # 面试纪要、转写稿
└── .gitkeep                        # 示意用占位
```

> `roster.json`（在职花名册）和 `events.log`（追加式事件日志）正式启用时再行落地，README 中暂未涉及。

## 当前状态

- 目录已创建（运行期 `~/.openclaw-hr/common/` 与课程仓库 `hr_claw_hub/openclaw-hr/common/` 两份同名同步）
- 内容为空，仅有本 README
- 任何业务子 Agent 不要直接读写此目录；后续由对应的 Skill 入口操作

## 与现有 workspace 的关系

- 本目录**不属于**任何 `workspace-<id>/`，各业务 Agent 工作区内容依旧自治
- 已有 demo 数据保留在原位置（`workspace-recruitment/ inbox|parsed|profiles` 等）
- 真正落地时再做演示数据迁移，迁移方案待后续评估
