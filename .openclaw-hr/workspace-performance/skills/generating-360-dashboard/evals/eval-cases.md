# generating-360-dashboard 评测场景

> 评测对象：从同目录 `aggregated-data.json`（评分）+ `aggregated-report.md`（语义）生成单文件 HTML 看板。

## 评测场景

### 场景 1 · 正常双输入生成看板（happy path）

- 输入：`feedback-360/source_feedback/<slug>/` 下同时有 `aggregated-data.json` 与 `aggregated-report.md`（如 `yuangong1/`）
- query：把员工1的 360 反馈做成一张可视化看板
- expected_behavior：
  - 跑 `build_dashboard.py <slug目录>`，产出同目录 `report.html`
  - **评分/极差**只读 JSON；**判定与卡片**解析 `aggregated-report.md` 并吸入 HTML
  - 看板含五个模块：合规 banner、四视角雷达图、五维度对照表、共识/分歧卡片、看板用途
  - 判定与报告总览一致（含「边界共识」→ 共识），**不**照搬 JSON `suspected_split`
  - 页脚有 `aggregated-data.json` 的 md5；页面不外链要求读者再打开 md

### 场景 2 · 责任心：报告边界共识 vs 机械极差

- 输入：责任心视角极差 1.00、报告标「边界共识」的样本目录
- expected_behavior：
  - 「极差」列照实显示 JSON 的 1.00
  - 「判定」列为**共识**（来自报告「边界共识」），不是机械分歧
  - 卡片文案来自报告「**判定**」段

### 场景 3 · 数字只取不算

- 看板所有评分与 `aggregated-data.json` 的 `perspectives` 段逐项一致
- 页脚 md5 锁定数据源版本

### 场景 4（边界）· 输入缺失或非法

- 路径不存在 → 退出码 2
- JSON 非法 / 缺 perspectives → 退出码 1
- **缺 `aggregated-report.md` → 退出码 1**（明确报「语义必须来自报告」）

### 场景 5 · 发布到 Canvas

- 调用 `build_dashboard.sh ... --publish --force`
- canvas-id：`feedback-360-<slug>`
- 落盘 canvas documents 下 `index.html`；无 `--force` → exit 5
