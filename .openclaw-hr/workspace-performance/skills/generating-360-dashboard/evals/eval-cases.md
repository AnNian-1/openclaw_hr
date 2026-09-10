# generating-360-dashboard 评测场景

> 评测对象：从同目录 `aggregated-data.json`（评分）+ `aggregated-report.md`（语义）生成单文件 HTML 看板。
> 现行夹具：`feedback-360/source_feedback/yuangong1/`（4 份）。不要套课程 7 份张磊判定。

## 评测场景

### 场景 1 · 正常双输入生成看板（happy path）

- 输入：`feedback-360/source_feedback/yuangong1/`（同时有 JSON 与 md）
- query：把员工1的 360 反馈做成一张可视化看板，不要定级
- expected_behavior：
  - 入口：`build_dashboard.sh <slug目录>` 或 `build_dashboard.py <slug目录>`
  - 产出同目录 `report.html`
  - **评分/极差**只读 JSON；**判定与卡片**解析 `aggregated-report.md`
  - 看板含：合规 banner、四视角雷达图、五维度对照表、共识/分歧卡片、面谈输入定位
  - 现行报告判定：目标达成/责任心/学习成长 = 共识；专业能力/协作沟通 = 分歧
  - 页脚有 JSON md5；页头来源人数与 JSON `perspectives.*.count` 一致（现行是 4 份，不是「平级 3 + 下属 2」）
  - 全文无 S/A/B/C/D 定档

### 场景 2 · 责任心：报告共识 vs 机械极差

- 输入：现行 `yuangong1`（责任心视角极差 1.00、`suspected_split: true`，报告标共识）
- expected_behavior：
  - 「极差」列照实显示 1.00
  - 「判定」列为**共识**（来自报告），不是机械分歧
  - 卡片文案来自报告，不是写死的课程「对内暖、对外硬」夹具叙事
  - 不要把这张夹具看板说成校准会已确认的结果

### 场景 3 · 数字只取不算

- 看板所有评分与 `aggregated-data.json` 的 `perspectives` 段逐项一致
- 页脚 md5 锁定数据源版本

### 场景 4（边界）· 输入缺失或非法

- 路径不存在 → 退出码 2
- JSON 非法 / 缺 perspectives → 退出码 1
- **缺 `aggregated-report.md` → 退出码 1**（语义必须来自报告）
- 传入第三参 `verdict_json`：脚本忽略该文件，判定仍只读报告

### 场景 5 · 发布到 Canvas

- 调用 `build_dashboard.sh ... --publish --force`
- canvas-id：`feedback-360-<slug>`（例 `feedback-360-yuangong1`）
- 落盘 canvas documents 下 `index.html`；无 `--force` → exit 5
