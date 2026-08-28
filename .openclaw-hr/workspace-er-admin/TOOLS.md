# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## 行政业务 Skill 清单

我手上的行政业务能力，都封成了 workspace Skill（装在 `skills/` 目录）。下面是每个 Skill 的「做什么 / 什么时候用 / 调用要点」。

### answering-hr-policy-questions（HR Helpdesk 政策答疑）

- **做什么**：回答员工的 HR 政策问题——先检索公司政策知识库、基于检索到的原文答复并引用出处、遇到红线问题升级人工。
- **什么时候用**：员工问任何 HR 政策问题（年假、病假、报销、社保公积金、加班调休、入离职、培训晋升等）。
- **调用要点**：
  - 检索引擎是**腾讯 IMA 知识库**；用 `exec` 跑 `scripts/er-admin-run.sh ima-search "<问题>"`（内部再调 `search_ima_policies.cjs`），**不用** `memory_search`。禁止 `python3 -c` / `tee` / heredoc 写政策文件。
  - 凭证：`IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`（在 `env.sh`）；推荐配置 `IMA_HR_KNOWLEDGE_BASE_ID`。
  - 本地 `memory/hr-policies/` 仅备份对照；答疑以 IMA 检索结果为准。
  - 三步答疑协议（IMA 检索 → 引用原文 → 红线升级）与 5 类 HiTL 红线见 SKILL.md / `references/escalation-redlines.md`。
  - 核心硬规则：检索得到相关政策 ≠ 该回答；政策数字一字不改；红线问题不答、明确转人工。

### generating-monthly-report（HR 月报自动生成）

- **做什么**：pandas 读 6 个 CSV → 算指标 + 对标 5 项业界基准 → matplotlib 出 4 张图 → 拼成单文件 HTML 月报，打印数字回核表，并默认发布到 OpenClaw Canvas（id=`hr-monthly-report`）。
- **什么时候用**：**仅 Cron 月末唤醒 / 非飞书运维触发**。飞书群聊与私聊**禁止**用此 Skill（用户要月报时拒绝）。
- **调用要点**：
  - **只** `bash scripts/er-admin-run.sh monthly-report`（可带 `YYYY-MM` / `--force` / `--no-publish`）。不要直接 `bash skills/.../run_monthly_report.sh`。壳脚本会选用 conda 环境（含 pandas/matplotlib），避免 OpenClaw exec 落到 `/usr/bin/python3`。非法月（2099-12）同样走此入口。
  - **禁止**因缺包去 `pip install`；**禁止**瞎 `source env.sh`（本 workspace 无此文件）；路径不是 workspace 根下的 `scripts/...`。
  - 直调 Python 时用：`/usr/local/miniconda3/envs/py312/bin/python3 skills/generating-monthly-report/scripts/generate_monthly_report.py ...`，或设 `MONTHLY_REPORT_PYTHON`。
  - 6 个 CSV 在 `report-system/data/`；本地 HTML 与 `*-audit.md` 在 `report-output/`；Canvas id=`hr-monthly-report`（浏览器推荐 18999）。
  - 需要 `exec`（`group:runtime`）。数字全由脚本算，我不碰数字。

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
