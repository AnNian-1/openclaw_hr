# 月报数据源（HCM 单一来源）

现行：HCM 日常事实表 → freeze 计算指标 → 主题快照 `MonthlyReportMetricSnapshot` → GET → 小慧出报。禁止 CSV 生产回退、禁止 `/api/nodes` 写完成率等最终指标。

# 月报数据改从 HCM 读（演示闭环，历史）

**状态**：已落地（2026-09-09）。conda `openclaw-hr` 已装在 `/home/hr/miniconda3`。

## 环境

- Miniconda：`/home/hr/miniconda3`（用户 `hr`）
- 环境：`openclaw-hr`（Python 3.12 + pandas/matplotlib + HCM FastAPI 栈）
- 入口：`/home/hr/miniconda3/envs/openclaw-hr/bin/python3`
- **未装** `funasr_me`（面试转写，numpy&lt;2，不要混进本环境）
- 可再跑：`bash /home/hr/.openclaw-hr/scripts/install-miniconda-openclaw-hr.sh`

## 已验收

- `python seed.py`：6 张月报表 + 员工1
- `GET /api/reports/monthly` 月份 2025-12～2026-07
- `monthly-report --force --no-publish 2026-07` 审计来源为 `HCM GET /api/reports/monthly/2026-07`

图表中文缺字体（本机无 Noto CJK），数字回核已通过。前端 `:5174` 需 `hcm/frontend` 下 `npm install` 后 `bash start.sh`。
