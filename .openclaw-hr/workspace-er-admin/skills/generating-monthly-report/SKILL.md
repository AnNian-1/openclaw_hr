---
name: generating-monthly-report
description: Orchestrate publishing HR monthly report HTML from HCM frozen snapshot only. Ops CLI, not Feishu. run_monthly_report.sh POSTs HCM freeze then GET the same YYYY-MM. Do not read CSV or invent numbers.
metadata:
  openclaw:
    requires:
      bins: ["python3", "bash"]
---

# generating-monthly-report

把 **HCM 已冻结** 月报生成 HTML 并发布 Canvas。本 Skill **只编排发布**，不写业务取数。唯一取数系统是 HCM。

`run_monthly_report.sh` 先 `POST /api/reports/monthly/{YYYY-MM}/freeze`，再把同一月份传给生成器。无冻结或事实不足则失败，不读 CSV、不填 0。你（er-admin）到点跑脚本，不碰数字。

## 何时用

- **宿主机日检** — `scripts/maybe-monthly-report.sh` 或 `/opt/hr-ops/maybe-monthly-report.sh`：明天是否为 01（Asia/Shanghai）。
- **手动补跑** — 运维 CLI。飞书禁止。

## 推荐入口

对话/`exec` **只跑** `bash scripts/er-admin-run.sh monthly-report [YYYY-MM] [--force] [--no-publish]`。

```bash
bash skills/generating-monthly-report/scripts/run_monthly_report.sh 2026-07 --no-publish
```

必须带月份。不要系统 `python3` / 不要 `pip install`。

## 工作流程

1. 确认触发 → `run_monthly_report.sh YYYY-MM`
2. 脚本 POST HCM freeze，再生成 HTML + audit
3. 默认发布 Canvas id=`hr-monthly-report`
4. 不改数字

浏览器：`http://127.0.0.1:18999/__openclaw__/canvas/documents/hr-monthly-report/index.html`

细则 → `references/report-pipeline.md`

## 关键规则

- 数字全部由脚本从 HCM 冻结 payload 计算。
- 回核表指向 HCM 冻结快照与 `report_run_id`。
- 「统计中」不是错误。
- Canvas id 只用 ASCII `hr-monthly-report`。
