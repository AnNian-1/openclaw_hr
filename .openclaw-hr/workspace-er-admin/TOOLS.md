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
  - 检索引擎是**腾讯 IMA 知识库**；用 `exec` 跑 `scripts/er-admin-run.sh ima-search "<问题>"`，**不用** `memory_search`。禁止 `python3 -c` / `tee` / heredoc 写政策。冒烟报告用 write 写到 `docs/qa/`。
  - 凭证：`IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`（在 `env.sh`）；推荐配置 `IMA_HR_KNOWLEDGE_BASE_ID`。
  - 本地 `memory/hr-policies/` 仅备份对照；答疑以 IMA 检索结果为准。
  - 三步答疑协议（IMA 检索 → 引用原文 → 红线升级）与 5 类 HiTL 红线见 SKILL.md / `references/escalation-redlines.md`。
  - 核心硬规则：检索得到相关政策 ≠ 该回答；政策数字一字不改；红线问题不答、明确转人工。
  - 飞书 HR / WebChat / CLI 查**别人**的合同薪资：不要用本 Skill，改用 `querying-employee-payroll`。

### querying-employee-payroll（花名册合同薪资）

- **做什么**：按 HCM 花名册（HCM 不可用则入职 stub）查出别人的合同薪资。不编姓名、不编金额。
- **什么时候用**：WebChat / CLI，或飞书 HR，问「员工1工资多少」「花名册薪资」。
- **调用要点**：
  - 只 `bash scripts/er-admin-run.sh payroll-query [--sender <ou_>] --name 员工1` 或 `--all`。
  - 飞书必须传会话 `ou_`；WebChat / CLI 省略 `--sender`。
  - 主管/员工 ou_ 会被脚本拒绝（退出码 3）。
  - 只念 JSON 的 `people[]`；没有此人就说没有，不要补数。

### generating-monthly-report（HR 月报自动生成）

- **做什么**：POST HCM freeze → GET 冻结 payload → pandas 展示计算 → HTML。不读 CSV。
- **什么时候用**：运维 CLI / OpenClaw cron `hr-monthly-report-push`（月末 23:59）。飞书会话禁止出月报。
- **调用要点**：
  - **只** `bash scripts/er-admin-run.sh monthly-report [--sender <ou_>]`（可带 `YYYY-MM` / `--force` / `--no-publish`）。不要直接 `bash skills/.../run_monthly_report.sh`。壳脚本会选用 conda 环境（含 pandas/matplotlib），避免 OpenClaw exec 落到 `/usr/bin/python3`。非法月（2099-12）同样走此入口。
  - 月度**推送**（cron 自动触发 / 手动演示）：**只** `bash scripts/er-admin-run.sh monthly-report-push [--period YYYY-MM]`，其 stdout 即推送正文。不要直接 `bash skills/.../notify_monthly_report.sh`。
  - **禁止**因缺包去 `pip install`；**禁止**瞎 `source env.sh`（本 workspace 无此文件）；路径不是 workspace 根下的 `scripts/...`。
  - 直调 Python 时用 conda `openclaw-hr` 或 `MONTHLY_REPORT_PYTHON`。
  - 演示 fixture 在 `report-system/tests/fixtures/monthly-report/`；产出在 `report-output/`；Canvas id=`hr-monthly-report`（浏览器推荐 18999）。
  - 需要 `exec`（`group:runtime`）。数字全由脚本算，我不碰数字。招聘/培训权威分别是 ATS/LMS，不是 HCM。

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
