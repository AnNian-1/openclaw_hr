# aggregating-360-feedback 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：从压缩包摄入 DOCX → JSON，再机械聚合成按视角分组的 aggregated-data.json。

## 评测场景

### 场景 0 · 压缩包摄入（DOCX → JSON）

- 输入：`feedback-360/source_feedback/` 顶层任意文件名的 `.zip`/`.rar`（内含已填 DOCX）
- query：把这包 360 反馈表解压并解析成 JSON
- expected_behavior：
  - 跑 `ingest_archive.py`（可无参自动发现，或显式传任意包名）
  - 落盘到 `source_feedback/<被评估人目录>/`（由 DOCX「被评估人」决定，与压缩包名无关）
  - 产出 manager / peer-* / report-* / self JSON
  - 各份 `reviewer_alias` 为 领导1 / 同事N / 下属N / 自评（即使 DOCX 里写了人名也会被改写）
  - 退出码 0

### 场景 1 · 正常 7 份反馈（happy path）

- 输入：场景 0 产出的 `source_feedback/yuangong1/`（或等价合法 JSON 目录）
- query：把这组 360 反馈聚合一下，给绩效面谈用
- expected_behavior：
  - 先跑 `check_feedback.py` 校验，7 份全部合法
  - 跑 `aggregate.py` 产出 `source_feedback/<slug>/aggregated-data.json`
  - `perspectives` 段含 manager/peer/report/self 四组，逐维度有 average/min/max
  - `divergence` 段把协作沟通（极差 1.50）、责任心（极差 1.00）、学习成长（极差 2.00）三个维度标 `suspected_split: true`
  - 终端对照表读数与同目录 `aggregated-data.json` 一致
  - 综合分析报告约定路径：`source_feedback/<slug>/aggregated-report.md`

### 场景 2 · 脏数据：评分越界 + 缺维度

- 输入：一份反馈的 `collaboration` 评分被改成 7（越界）、`growth` 维度被删
- query：把这组反馈聚合
- expected_behavior：
  - `check_feedback.py` 在聚合前抓出两个问题——评分非法、缺维度，退出码 1
  - 不进入聚合步骤，不产出基于脏数据的 `aggregated-data.json`
  - Agent 据报错说明数据有问题，而不是硬聚合

### 场景 3 · 视角不完整：缺自评

- 输入：只有 manager + peer 两份反馈，没有 self
- query：把这组反馈聚合
- expected_behavior：
  - `check_feedback.py` 抓出「缺少自评视角」，退出码 1
  - 说明 360 反馈必须含上级和自评视角，数据不完整不能聚合

### 场景 4（边界）· 空目录 / 目录不存在 / 坏压缩包

- 输入：空目录、不存在的路径，或损坏的 zip
- query：摄入或聚合
- expected_behavior：
  - 脚本报错退出（空目录退出 1、目录/文件不存在退出 2、坏包退出 1）
  - 不产出虚假的聚合结果

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-f1-skillified.md` CP1 · 步骤 2。
