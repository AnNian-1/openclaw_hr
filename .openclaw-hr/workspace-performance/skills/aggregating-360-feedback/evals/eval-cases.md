# aggregating-360-feedback 评测场景

> 评测对象：现行路径 `feedback-360/source_feedback/<slug>/`。
> 不要用课程 `raw/` + 根目录 `aggregated-data.json`，不要用张磊数字当现行夹具预期。

## 评测场景

### 场景 0 · 压缩包摄入（DOCX → JSON）

- 输入：`feedback-360/source_feedback/` 顶层任意名 `.zip`/`.rar`（内含已填 DOCX）
- query：把这包 360 反馈表解压并解析成 JSON
- expected_behavior：
  - 跑 `ingest_archive.py`（可无参自动发现，或显式传路径）
  - 落盘到 `source_feedback/<slug>/`（由 DOCX「被评估人」决定）
  - `reviewer_alias` 为 领导1 / 同事N / 下属N / 自评
  - 退出码 0

### 场景 1 · 现行夹具 happy path（员工1 / yuangong1）

- 输入：`feedback-360/source_feedback/yuangong1/`（现行 **4** 份：manager / peer-01 / report-01 / self）
- query：把员工1的 360 反馈校验一下，不要定级
- expected_behavior：
  - `check_feedback.py feedback-360/source_feedback/yuangong1` 退出码 0
  - 若跑 `aggregate.py`：写出同目录 `aggregated-data.json`（已有夹具时先备份）
  - `perspectives` 含 manager/peer/report/self；评估人代号为 领导1/同事1/下属1/自评
  - 机械极差（以脚本打印 / JSON `divergence` 为准，不要背课程 7 份数字）：
    - 目标达成 1.00、专业能力 1.00、协作沟通 1.00、责任心 1.00 → `suspected_split: true`
    - 学习成长 0.00 → `suspected_split: false`
  - **禁止**输出 S/A/B/C/D
  - 历史 7 份样例在 `yuangong1.bak/` 与 `feedback-360/models/`，不是现行入口

### 场景 2 · 脏数据：评分越界 + 缺维度

- 输入：临时目录；`collaboration` 改成 7、删掉 `growth`
- query：把这组反馈聚合
- expected_behavior：
  - `check_feedback.py` 退出码 1（评分非法、缺维度）
  - `aggregate.py` 同样退出码 1，**不写出** `aggregated-data.json`
  - 不要改用 `feedback-360/check_feedback.py`（无参、绑 raw/）

### 场景 3 · 视角不完整：缺自评

- 输入：临时目录，只有 manager + peer，没有 self.json
- query：把这组反馈聚合
- expected_behavior：
  - `check_feedback.py` 抓出「缺少自评（self）反馈」，退出码 1
  - `aggregate.py` 同样拒绝，退出码 1，不写聚合
  - 说明 360 必须含上级和自评

### 场景 4（边界）· 空目录 / 目录不存在

- 输入：空目录、不存在的路径
- expected_behavior：
  - 空目录退出 1；目录不存在退出 2
  - 不产出虚假聚合结果

## 基线说明

课程评测里「7 份 / 协作 1.50 / 责任心 1.00 / 成长 2.00」对应历史样例，不是现行 `yuangong1`。
