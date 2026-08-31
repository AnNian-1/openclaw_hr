# 月报 Pipeline 细则

本文件是 generating-monthly-report Skill 的 Pipeline 细则——SKILL.md 正文给出两个脚本的用法和硬规则，这里给数据契约、产出结构、Cron 投产配置的细节。

## 6 个 CSV 数据源（输入契约）

月报的输入是 report-system/data/ 下的 6 个 CSV，各管一块 HR 业务。脚本对它们的列名有约定——换公司数据时文件名和被直接读取的列名要对得上，数值随便换。

| CSV 文件 | 结构 | 覆盖内容 |
|---------|------|---------|
| recruitment-funnel.csv | 按月一行 | 招聘漏斗：投递数、初筛通过、面试、Offer、入职、各级转化率 |
| positions-progress.csv | 按岗位一行（当期快照）| 在招岗位的 HC、已入职、在招中、平均在招天数、招聘状态 |
| onboarding-retention.csv | 按月一行 | 入职人数、试用期通过、45 天内离职、45 天内离职率、备注 |
| training-completion.csv | 按月一行 | 应参训/完成人数、完成率、培训满意度、主要培训内容 |
| hiring-cost.csv | 按月一行 | 招聘渠道费用、人均招聘成本、平均 TimeToHire 天数 |
| attrition.csv | 按月一行 | 离职总人数、主动/被动离职、月离职率、各类离职原因 |

注意 6 个 CSV 有两种结构：5 个是「按月一行」的时间序列，positions-progress.csv 是「按岗位一行」的当期快照。换数据时各自保持原结构。

## 脚本怎么取数

脚本从 CSV 取数有两种方式：

- 直接读列：如「投递数」列、「面试转Offer率」列原样取出。
- 脚本自己算：如「整体到位率」= 已入职合计 / 岗位总HC，「初筛到面试」转化率用相邻两级数量相除。CSV 里没有这些列。

不管哪种，每个进入 HTML 的数字都会在脚本的 audit 列表里追加一条 (指标名, 值, 来源)——这就是数字回核表。

## 产出

- report-output/hr-monthly-report-<月份>.html —— 单文件 HTML 月报（约 156 KB），4 张图表（招聘漏斗、6 月趋势线、成本柱状、离职饼图）全部 base64 内嵌，不依赖外部图片。作为邮件附件发送（不要贴成正文，base64 图会被邮件客户端当安全风险拦掉）。
- report-output/hr-monthly-report-<月份>-audit.md —— 数字回核审计文档，与 HTML 同目录落盘；18 项进 HTML 的数字逐条列出 CSV / 算式来源。终端仍会同步打印同一张表。
- Canvas 文档 —— 默认（`run_monthly_report.sh` 或 `--publish --force`）发布到 `$OPENCLAW_STATE_DIR/canvas/documents/hr-monthly-report/index.html`（优先 `~/.openclaw-hr/canvas/...`）。浏览器推荐：`http://127.0.0.1:18999/__openclaw__/canvas/documents/hr-monthly-report/index.html`。细则见 `canvas-publishing.md`。

## 业界对标基准

脚本里 BENCHMARK 字典写死 5 项业界基准：面试到Offer 转化率 27%、Offer 接受率约 50%、Time to Hire 43 天、入职 45 天内离职率 20%（SHRM）、培训满意度 4.0（Kirkpatrick L1）。其中两项画进趋势线（叠橙色基准虚线），5 项汇成「对标业界基准」表（逐项标「达标 / 需关注」）。换基准改这个字典。

## 数字真实性纪律（本 Skill 的核心价值）

HR 月报是给管理层做判断用的，数字错一个、下游判断就跟着错。本 Skill 的设计纪律：

- 所有数值由 pandas 脚本确定性算出，LLM 完全不碰数字。同样的 CSV 跑一万次结果完全一致，可逐行复核。
- LLM（被 Cron 唤醒的 er-admin）只负责一件事——到点把脚本跑起来。不复述数字、不改写数字、不生成数字。
- 数字回核表是「LLM 没碰数字」的证据。18 项数字逐条指回 CSV 单元格或一个可验算的算式，谁拿到月报都能 30 秒核一遍。
- 「统计中」是诚实的体现。5 月入职员工还在 45 天观察期，结果未产生——脚本如实标注「统计中」，不硬凑数字。

## Cron 投产配置

月报真正投产由 OpenClaw Cron 月末定时唤醒 er-admin 执行。生产注册命令：

    openclaw cron add \
      --name "hr-monthly-report" \
      --cron "59 23 28-31 * *" \
      --tz "Asia/Shanghai" \
      --session isolated \
      --agent er-admin \
      --message "运行月报 Skill 的 run_monthly_report.sh 生成本月 HR 月报并发布到 Canvas"

两个细节：

- 月末守卫：59 23 28-31 * * 在每月 28-31 日各触发一次，但 run_monthly_report.sh 的月末守卫判断「明天是否 1 号」，只有真月末当天才生成、其余空跑退出。这是标准 cron 实现「仅月末跑一次」的可移植做法（cron 的 L 修饰符并非所有调度器都支持）。
- 时区：必须带 --tz "Asia/Shanghai"，否则 23:59 按 UTC 理解会变成北京时间次日 07:59。且 cron 求值时区要和守卫脚本读的系统时区一致。

## 非 macOS 环境（中文字体 / Python）

### Python 解释器（OpenClaw exec 易踩坑）

`exec` 里的 `python3` 常是 `/usr/bin/python3`，**没有** pandas/matplotlib；课程依赖装在：

`~/miniconda3/envs/openclaw-hr/bin/python3`

请用 `run_monthly_report.sh`（内置 `resolve_python`），或设 `MONTHLY_REPORT_PYTHON`。**不要**对系统 Python `pip install`。

### 中文字体

matplotlib 图表中文依赖本机字体。脚本 `_setup_chinese_font()` 按顺序探测：

1. Skill 自带 `scripts/fonts/NotoSansCJKsc-Regular.otf`（推荐，已随仓库/Skill 交付）
2. Linux：Source Han Sans / 文泉驿 / Noto CJK 常见路径
3. macOS：PingFang / STHeiti / Hiragino
4. Windows：微软雅黑 / 黑体

旧版只写 macOS 路径时，Linux 会静默回退 DejaVu Sans，**图表 PNG 里中文变成方框**（HTML 正文一般仍正常）。脚本已设 matplotlib Agg 后端，无图形界面环境（如 Cron 唤醒的 isolated 会话）也能正常出图。
