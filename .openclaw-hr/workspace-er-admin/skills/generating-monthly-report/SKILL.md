---
name: generating-monthly-report
description: Generate the company HR monthly report as a single-file HTML with charts, then publish it to OpenClaw Canvas host for browser viewing. Use this skill whenever an HR monthly report is needed - either when woken by a month-end Cron job, or when asked for a specific month's report. Prefer bash scripts/run_monthly_report.sh (it selects conda py312 with pandas/matplotlib). Do not pip install dependencies. It runs a deterministic pandas pipeline that reads 6 HR CSV files, computes metrics, benchmarks them against 5 industry baselines, draws 4 matplotlib charts, assembles a single-file HTML report, and copies it to canvas/documents/hr-monthly-report/index.html (ASCII id required; view via nginx 18999). It also prints a number-audit table tracing every figure in the report back to its CSV source. All numeric values are computed deterministically by the script - the LLM never touches the numbers.
metadata:
  openclaw:
    requires:
      bins: ["python3", "bash"]
---

# generating-monthly-report

把公司当月的 HR 数据生成成一份图文 HTML 月报，并发布到 OpenClaw Canvas 供浏览器查看——pandas 读 6 个 CSV、算指标、对标业界基准、出 4 张图、拼成单文件 HTML、打印数字回核表，再落盘到 Canvas。

这是一个**脚本型 Skill**：核心是 `scripts/` 下的脚本。月报的所有数字由 pandas 确定性算出——你（er-admin）的角色只有一个：到点把脚本跑起来，不碰数字、不改写、不复述生成数字。

## 何时用这个 Skill

需要生成 HR 月报时用，两种触发场景：

- **被 OpenClaw Cron 月末定时唤醒** —— 生产环境每月 28-31 日 23:59 触发，生成本月月报并发布 Canvas。
- **手动要某个月的月报** —— 临时需要补某月或重出某月的月报。

## 推荐入口（务必用这个）

对话/`exec` **只跑** `bash scripts/er-admin-run.sh monthly-report [YYYY-MM] [--force] [--no-publish]`（内部再调 `run_monthly_report.sh`）。不要直接 `bash skills/.../run_monthly_report.sh`（不在 allowlist）、不要系统 `python3` / 不要 `pip install` / 不要用 `tee` 写 md。非法月（如 2099-12）也走同一入口，把脚本失败原文交回。

OpenClaw `exec` 的 PATH 常把 `python3` 解析成 `/usr/bin/python3`（无 pandas）；依赖已装在 conda `py312`。壳脚本会自动选用：

`/usr/local/miniconda3/envs/py312/bin/python3`

（可用环境变量 `MONTHLY_REPORT_PYTHON` 覆盖。）

脚本真实路径（相对 er-admin workspace 根）：

```bash
bash skills/generating-monthly-report/scripts/run_monthly_report.sh
bash skills/generating-monthly-report/scripts/run_monthly_report.sh 2026-07
bash skills/generating-monthly-report/scripts/run_monthly_report.sh --force --no-publish
```

**不要**使用 `scripts/generate_monthly_report.py`（workspace 根下没有这个路径）。  
**不要** `source env.sh`（本 workspace 无此文件）。  
**不要**因 `ModuleNotFoundError: pandas` 去 `pip install`——那是用错了系统 Python。

### generate_monthly_report.py —— 月报生成本体

仅在已确认解释器时直调（一般不必）：

```bash
/usr/local/miniconda3/envs/py312/bin/python3 \
  skills/generating-monthly-report/scripts/generate_monthly_report.py 2026-07 --publish --force
```

`run_monthly_report.sh` 内部调的就是它；另有副本在 `report-system/generate_monthly_report.py`（数据同目录时也可，但仍须用 conda python）。

## 工作流程

1. **确认触发场景**：Cron / 手动 → **一律** `bash skills/generating-monthly-report/scripts/run_monthly_report.sh`（可带月份 / `--force` / `--no-publish`）。
2. **执行脚本**：读 `report-system/data/` 下 6 个 CSV → 算指标 → 出图 → HTML + `report-output/hr-monthly-report-<月份>-audit.md`。
3. **发布到 Canvas（默认）**：id=`hr-monthly-report`；审计 md 只留本地。
4. **核对产出**：HTML、audit、退出码 0；终端有回核表与 Canvas URL。
5. **不改动数字**。

浏览器查看：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/hr-monthly-report/index.html
```

可选 embed：`[embed ref="hr-monthly-report" type="canvas/document"]`

细则 → `references/report-pipeline.md`、`references/canvas-publishing.md`

## 关键规则（这几条必须守死）

- **数字全部由脚本算，你完全不碰数字。**
- **数字回核表原样保留**（终端打印 + `report-output/*-audit.md`）。
- **「统计中」不是错误，不要去补。**
- **优先 `run_monthly_report.sh`；禁止 `pip install pandas/matplotlib`。** 缺包多半是 `/usr/bin/python3`，应改用壳脚本或 conda 绝对路径。
- **Canvas id 只用 ASCII `hr-monthly-report`。**

## 这个 Skill 不做什么

- 不做政策答疑——那是 `answering-hr-policy-questions` Skill。
- 不自动把月报推送到邮箱 / IM——默认只生成到 `report-output/` 并发布 Canvas。
- 不替 LLM 写月报文字——文字解读由脚本基于确定性指标拼装。
- 不负责给系统 Python 装依赖。
