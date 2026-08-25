---
name: generating-minutes
description: Turn a speaker-separated interview transcript into a structured interview minutes document, with the candidate's spoken numbers audited against their original resume. Use this skill after transcribing-interviews has produced a speaker-labelled transcript, to get key Q&A organized by speaker, candidate strengths, concerns, highlights and a hiring recommendation. A large model writes the minutes; a deterministic step then traces every number the candidate quoted back to the original resume so fabricated or misremembered figures are flagged. It generates and audits the minutes — it does not transcribe audio or do compliance filtering.
metadata:
  openclaw:
    requires:
      bins: ["python3", "node"]
---

# generating-minutes

把 `transcribing-interviews` 产出的"按发言人标注的转写稿"，整理成一份结构化的面试纪要——关键问答、候选人优势、待考察点、高亮时刻、评分建议。这是面试纪要链路的第二段、也是最后一段。

## 何时用这个 Skill

收到一份按发言人组织的面试转写稿（`transcribing-interviews` 的产物），需要把它变成 HR 能直接用的结构化纪要时用。

它和纪要链路里另一个 Skill 边界清楚：本 Skill 的输入是**转写稿**，不是音频——录音转文字、分说话人是 `transcribing-interviews` 的事。本 Skill 只做"转写稿 → 结构化纪要"，不做转写、不做合规过滤。

## 为什么转写稿还不够，要再整理一次

转写稿是流水账——它如实记下了每句话，但 HR 真正要的不是流水账，是**提炼后的纪要**：哪些是关键问答、候选人有什么优势和短板、能不能给评分建议。一场 40 分钟二面的转写稿几千字，人工提炼成纪要要花 1-2 小时。这个 Skill 把这件事交给大模型几十秒做完——这是"AI 超越人工"的体现。

## 工作流程

纪要生成分两步，按顺序做：

### 第 1 步 · 生成纪要 + 数字回核

```bash
python3 skills/generating-minutes/scripts/gen_minutes.py \
  interview/<转写名>.json inbox/<候选人简历>.md \
  interview/<纪要名>.json interview/<纪要名>.md \
  --candidate <姓名> --position <岗位> --round <轮次> \
  --interviewer speaker_A
```

脚本做三件事：

1. **按说话人重组转写稿**——把连续的同说话人片段合并成对话稿。
2. **大模型生成结构化纪要**——调 DeepSeek V4，产出关键问答 / 优势 / 待考察点 / 高亮时刻 / 评分建议，并提取候选人口述的项目数字。
3. **数字回核**——把纪要里候选人口述的数字逐项对照原简历核对，能追溯的标"可追溯"，找不到的标"需人工核实"。

关于 `--interviewer`：转写稿里的说话人标签是 `speaker_A` / `speaker_B`（CAM++ 凝聚聚类只知道有 N 个人、不知道谁是面试官）。`--interviewer` 指定哪个标签是面试官，默认 `speaker_A`——按面试录音里通常面试官先开口的惯例。如果生成的纪要里"面试官说的话"和"候选人说的话"明显反了，把它换成 `speaker_B` 重跑。

跑脚本需要 `exec` 工具（`group:runtime` 权限组），并依赖环境变量 `DEEPSEEK_API_KEY`。

### 第 2 步 · 校验

纪要产物必须用校验脚本过一遍，跑通才算纪要合格：

```bash
node skills/generating-minutes/scripts/validate_minutes.js interview/<纪要名>.json
```

脚本校验：JSON 可解析、必需字段齐全、**关键问答每组都是"面试官问题—候选人回答"两行结构**、评分建议含 verdict（通过/待定/不通过）+ reason、**数字回核统计自洽**（回核确实逐项跑过，不是大模型编一个摘要）。退出码 0 = 通过，1 = 不通过（列出全部问题），2 = 用法错误。

校验不通过就按报出的问题处理，重跑第 1 步，直到校验通过。

## 关键规则

- **数字回核里大模型只"提取"、不"判真伪"**。候选人口述的数字由大模型从转写稿里提取出来，但"这个数字是真是假"由脚本对照原简历判定——大模型生成自由文本时会把数字记错或张冠李戴，真伪交给确定性脚本兜底。
- **回核基准是候选人的原简历**。纪要里候选人口述的项目数据（TPS、降幅、规模），必须能在他自己的简历里追溯。
- **数字回核有一个已知局限**：回核脚本只匹配阿拉伯数字。候选人口述的中文数字表述（"千分之三""十万分之二"）回核脚本抓不到，会标"无阿拉伯数字"——这不是漏判成"虚构"，是诚实标注"这一项脚本没覆盖、需人工看"。生产环境可在回核前加中文数字归一化。
- **关键问答必须按发言人组织**。每组关键问答都是"面试官提问 + 候选人回答"两行——这是面试纪要的硬要求，`validate_minutes.js` 会校验这个结构。
- **评分建议只是建议**。纪要给的是"通过/待定/不通过"建议，候选人最终去留由人工面试官决定（个保法 24 条 · HiTL）。纪要 Markdown 末尾固定带这条合规说明。

数字回核的判定逻辑、ASR 误识纠错、说话人标签映射细则见 → `references/minutes-method.md`
