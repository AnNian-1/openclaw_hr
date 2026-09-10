---
name: auditing-numbers
description: Audit a scoring result for fabricated numbers by checking every number in the scoring text against the candidate's own resume. Use this skill as the third and final stage of the scoring pipeline, after scoring-candidates has produced highlights, concerns, rationale and dimension reasons. It extracts each number in the scoring text, looks it up in the original resume, lets the model judge whether unmatched numbers are real fabrications, and rewrites confirmed fabrications back to the resume's true value with a minimal edit. The baseline is the candidate's own resume only — never the job description. This audits the scoring model's retelling of the resume; it does not score, filter sensitive fields, or check whether the resume itself is truthful.
metadata:
  openclaw:
    requires:
      bins: ["node"]
---

# auditing-numbers

对一份评分产出做数字回核——评分文字（亮点、顾虑、评分理由、各维度理由）里凡是引用候选人简历的数字，必须能在该候选人的原简历里找到对应值。对不上的判为虚构，修正回原简历真实值。这是评分 Pipeline 的第三层、也是最后一层。

## 何时用这个 Skill

评分产出经 `scoring-candidates` 生成之后用。它是评分 Pipeline 三层里的第三层，前面两层是合规过滤、8 维评分。任何一份要交到 HR 手里的评分结果，都要先过这一层。

它和相邻的几个 Skill 边界清楚：

- 它**不评分**——8 维度打分是 `scoring-candidates` 的事。本 Skill 的输入是评分产出，不是简历。
- 它**不做合规过滤**——剥离敏感字段是 `filtering-sensitive-fields` 的事。
- 它**不核简历本身真不真**——这是 `auditing-extraction`（简历解析的真实性核对）的事。本 Skill 回核的是"评分模型有没有如实复述简历"，不是"候选人有没有如实写简历"。如果候选人自己在简历里把数字吹大了，以简历为基准是核不出来的——那属于硬伤识别和面试环节的范畴。

本 Skill 只负责一件事：抓出评分文字里被大模型写错、串台的数字。

## 为什么需要这一层

评分第二层用大模型生成亮点、评分理由这些自由文本时，大模型会在"复述"候选人简历时把数字串台。实测案例——员工1原简历写"大促峰值 12.8 万 TPS"，评分 `highlights` 复述成了"双十一峰值 58 万笔/秒"。追因发现：58 万笔/秒 这个数字出现在**岗位 JD** 里，大模型把 JD 的场景数字张冠李戴安到了候选人头上。

这是大模型自由文本生成的典型**上下文串台**风险：两份内容相关的文档同时在上下文里，大模型复述其中一份时会把另一份的细节混进来。评分产出是 HR 做面试和录用判断的依据，里面每个数字都必须是真的。靠 prompt 叮嘱大模型"如实复述"不可靠——它不是故意撒谎，是生成机制决定了它会概率性地犯。要堵住它，得在大模型产出**之后**加一道独立的、每次评分都固定执行的核对层。

## 工作流程

对一份评分结果 + 该候选人的原简历，跑回核脚本：

```bash
bash scripts/recruitment-run.sh node skills/auditing-numbers/scripts/audit_numbers.js <评分结果json> <候选人原简历md> [修正后输出json]
```

脚本分四步：

1. **extract（抽取）**——从评分文字里正则抽出所有"数字 + 上下文短语"。确定性。
2. **verify（比对）**——每个数字在原简历里归一化比对。确定性。
3. **adjudicate（判定）**——简历里找不到的数字，交大模型逐个判定是不是真虚构（排除通用表述、约数、JD 场景数字）。这一步是大模型调用，非确定性。
4. **apply（修正）**——判为虚构的，用大模型给的最小替换对精确修正，留存修正前后快照。

退出码 0 = 回核完成（含"发现并修正了虚构数字"也算完成）；1 = 回核失败（大模型判定多次重试仍不可用——绝不当作"无虚构"放行）；2 = 文件/用法问题。

回核三步的性质差异、最小替换对怎么做、为什么基准只能是原简历，细则见 → `references/audit-method.md`

## 关键规则

- **回核基准只能是候选人的原简历，绝不能用 JD**。JD 里的数字看起来"相关"，但它属于岗位、不属于候选人——而且 JD 恰恰是串台的来源。脚本签名只吃简历、不留 JD 参数位，从机制上杜绝基准被污染。
- **数字回核每次评分都要跑，不能做成偶尔抽查**。大模型串台是非确定性的——同一份简历，有的批次串、有的批次不串，无法预测。只有每次都跑固定回核，才能保证交到 HR 手里的产出干净。
- **回核只修正虚构数字，不改综合分**。它改的是评分文字里串台的数字，评分分值由 `scoring-candidates` 决定，本 Skill 不碰。
- **大模型判定失败必须显式报错**。adjudicate 是非确定性的一步，多次重试仍失败时退出码非 0——绝不能把"判定没拿到"静默当成"无虚构"放行。
- **每处修正留存 text_before / text_after 两份快照**，写进回核报告——这是可审计、可追溯的合规证据。
