# generating-minutes 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把按发言人标注的转写稿，整理成结构化面试纪要，并对候选人口述数字做回核。

## 评测场景

### 场景 1 · 标准转写稿（一场完整技术二面）

- 输入：`interview/transcript-skilltest.json`（transcribing-interviews 产出的张磊技术二面转写稿，**105 片段**，speaker_A / speaker_B 两类，FunASR + CAM++ 输出）+ `inbox/resume-tech-01-张磊-后端开发.md`
- query：把这份转写稿整理成结构化面试纪要
- expected_behavior：
  - 产出纪要 JSON 含 candidate / position / qa / strengths / concerns / highlights / recommendation / mentioned_numbers / number_audit_summary
  - 关键问答（qa）每组都是"面试官问题—候选人回答"两行结构
  - 评分建议 recommendation.verdict 在 通过/待定/不通过 内 + 附 reason
  - 数字回核对候选人口述数字逐项核对，可追溯的标"可追溯"
  - 同步产出 Markdown 纪要，关键问答按发言人组织
  - `validate_minutes.js` 校验退出码 0

### 场景 2 · 数字回核——口述数字能在原简历追溯

- 输入：同场景 1
- query：生成纪要并核对候选人口述的数字
- expected_behavior：
  - 候选人口述的核心阿拉伯数字（80 万行、23 个服务、12.8 万 TPS、45 分钟→6 分钟）全部标"可追溯到原简历"
  - 中文数字表述（"千分之三""十万分之二"）标"无阿拉伯数字（回核脚本未覆盖）"——诚实标注，不漏判成虚构
  - number_audit_summary 的 total / traceable / needs_review 三者自洽

### 场景 3（边界）· 纪要结构缺失——数字回核统计造假

- 输入：一份 number_audit_summary.total 与 mentioned_numbers 实际条数不符的纪要 JSON（模拟大模型编了一个回核摘要、没真跑回核）
- query：校验这份纪要是否合格
- expected_behavior：
  - `validate_minutes.js` 报"number_audit_summary.total 与 mentioned_numbers 条数不一致——回核可能没真跑"
  - 退出码 1，不放行
  - 这道闸专门拦"假装做了数字回核"

### 场景 4（边界）· 输入文件缺失

- 输入：转写稿或简历缺一个
- query：生成纪要
- expected_behavior：
  - `gen_minutes.py` 报对应文件不存在，退出码 2
  - 大模型调用多次重试仍失败时退出码 1，绝不返回空纪要冒充成功

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c4-skillified.md` CP2 · 步骤 2。

基线痛点：没有这个 Skill，"整理纪要"就退化成"在 prompt 里写一长串纪要结构要求 + 数字回核要求"。每次都要重抄"按面试官—候选人组织关键问答""口述数字要对照简历核对""评分只给建议不做决定"这一整套；而且数字回核交给大模型自己做——它会"读一遍觉得对得上"就放过，没有逐字符比对，也没有可追溯率这个量化结果。没有校验闸，一份缺评分建议、或回核没真跑的纪要靠人事后才发现。
