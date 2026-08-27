# 评测场景 · generating-monthly-report

为 `generating-monthly-report` Skill 建的评测场景。方法基线 §五：评测先于文档，先测「没有 Skill 时的基线表现」找出该装的东西，再写最小 SKILL.md。

这是一个**脚本型 Skill**，评测可以「不经 Agent 单独跑脚本」隔离验证——验收点靠脚本的真实产出和退出码判定。

## 场景 1 · 指定月份生成月报（核心路径）

- 输入：`generate_monthly_report.py 2026-05`
- 验收点：
  - 退出码 0
  - `report-output/hr-monthly-report-2026-05.html` 生成（单文件 HTML，4 张图 base64 内嵌）
  - 同目录落盘 `report-output/hr-monthly-report-2026-05-audit.md`（18 项数字逐条带 CSV 来源）
  - 终端同步打印数字回核表；回核表数字与 6 个 CSV 原值逐条一致（2026-05 示例：投递 530、入职 8、**整体到位率 88.6%**（已入职合计 31 / 岗位总 HC 35）、离职率 1.6% 等）

## 场景 2 · 不指定月份（取最新月）

- 输入：`generate_monthly_report.py`（无参数）
- 验收点：
  - 自动取 CSV 里**最大 YYYY-MM**（当前夹具为 **2026-07**；CSV 增删月份后以此为准，勿写死旧月份）
  - 退出码 0，产出 HTML + audit.md；回核数字与该月 CSV 行一致

## 场景 3 · Cron 入口脚本的月末守卫（投产形态）

- 输入：`run_monthly_report.sh`（不带参数，模拟 Cron 月末逐日触发）
- 验收点：
  - 今天非月末时（明天不是 1 号）：打印「月末守卫拦截，空跑退出」，退出码 0，不生成月报
  - 带 `--force` 或带月份参数时：忽略月末守卫，立即生成
  - 这一步验证「28-31 日触发四次、只在真月末出一次报」的工业实现

## 场景 4 · 非法月份（边界）

- 输入：`generate_monthly_report.py 2099-12`（CSV 数据范围之外）
- 验收点：
  - 脚本识别月份不在数据范围，打印 `[ERROR] 月份 ... 不在数据范围`
  - 退出码 1（不产出垃圾 HTML）

## 场景 5 · 发布到 Canvas

- 输入：`generate_monthly_report.py 2026-05 --publish --force`（或 `run_monthly_report.sh 2026-05`）
- 验收点：
  - 调用 `publish_to_canvas.py`（经 generate 的 `--publish`）
  - canvas-id 为 ASCII `hr-monthly-report`（拒绝中文 id）
  - 落盘 `$OPENCLAW_STATE_DIR/canvas/documents/hr-monthly-report/index.html`（或 `~/.openclaw-hr/canvas/...`）
  - 终端打印 nginx / gateway 可访问 URL
  - `--no-publish` 时只写 `report-output/`，不碰 Canvas

## 评测设计说明

- 场景 1、2 测「月报核心生成路径」——脚本读 6 CSV → 算指标 → 出 HTML + 回核表。
- 场景 3 测「投产形态」——Cron 入口脚本的月末守卫，这是月报能无人值守的关键。
- 场景 4 测「边界」——非法输入不产出垃圾结果。
- 场景 5 测「Canvas 发布」——与入职看板同源的落盘约束。
- 数字真实性（数字回核表逐条对 CSV）是本 Skill 的核心价值，场景 1 的回核点直接对齐原实验 `exp-stage-f3-monthly-report.md` 的 18 项回核表。

