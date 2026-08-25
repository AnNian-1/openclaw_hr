---
name: answering-hr-policy-questions
description: Answer an employee's HR policy question by retrieving the company policy knowledge base on IMA (腾讯 IMA), replying strictly from the retrieved text, and escalating to a human when the question crosses a red line. Use this skill whenever an employee asks about HR policy — leave, attendance, reimbursement, social insurance, housing fund, probation, onboarding, offboarding, training, promotion, etc. This is a retrieval-grounded Q&A workflow: it forbids answering from the model's general knowledge, requires citing the source policy, and hard-stops on personal-data, dispute, legal, no-evidence, and approval cases that an AI must not decide.
metadata:
  openclaw:
    requires:
      bins: ["node"]
      env:
        - IMA_OPENAPI_CLIENTID
        - IMA_OPENAPI_APIKEY
---

# answering-hr-policy-questions

回答员工的 HR 政策问题——先检索公司政策知识库、严格基于检索到的原文答复、遇到红线问题升级人工。

这是一个**指令型为主、检索脚本为辅**的 Skill：答疑规程（引用出处、HiTL）写在本文；**检索引擎是腾讯 IMA 知识库**，通过本 Skill 的 `scripts/search_ima_policies.cjs` 调用 OpenAPI，**不再使用** OpenClaw `memory_search` / Builtin Memory。

## 何时用这个 Skill

员工通过企业微信等渠道问任何 HR 政策问题时用。典型场景：年假怎么算、病假规定、出差住宿报多少、加班餐能不能报、试用期有没有社保、公积金缴存比例、入离职流程、培训晋升通道。

## 前提：IMA 凭证与政策已入库（一次性设置，不属于本 Skill 答疑步骤）

1. **环境变量**（写在 profile 的 `env.sh`，不要写进本文件）：
   - `IMA_OPENAPI_CLIENTID`
   - `IMA_OPENAPI_APIKEY`
   - 推荐：`IMA_HR_KNOWLEDGE_BASE_ID`（固定 HR 政策知识库 ID，避免误选其它库）
2. **政策文档**已上传到该 IMA 知识库（00–13 行政政策等）。本地 `memory/hr-policies/` 仅作备份/对照。
3. 自检列出知识库：

```bash
node skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs --list-kb
```

**说明（易混点）：** IMA 网页/客户端问答走的是产品内 RAG；本 Skill 走 OpenAPI。`search_knowledge` 经常只返回文件名、`highlight_content` 为空。检索脚本会再调 `get_media_info` 拉取 Markdown 原文并抽取 `highlight`——与官方 `ima-skills` 读正文路径一致。

## 三步答疑协议（每个政策问题都照做）

收到员工的政策问题，按顺序走这三步。这是硬规程，不靠临场判断。

### 第 1 步 · 先检索，再回答

收到问题，用 `exec` 运行本 Skill 检索脚本（工作目录为 er-admin workspace 根）：

```bash
node skills/answering-hr-policy-questions/scripts/search_ima_policies.cjs "<员工原话或提炼后的检索词>"
```

- **严禁跳过检索凭印象答。** 必须先拿到脚本返回的 `hits`（含 `title` / `highlight`；`content_source=get_media_info` 表示已拉原文）。
- 脚本会自动短词改写 + `search_knowledge` 定位文档 + `get_media_info` 拉正文；一般**不必**再手搓第二轮检索。
- 若仍有 `warning` 且 `highlight` 为空：**不要补数字**，转人工。
- 脚本退出码非 0，或 `hit_count=0` / `ok=false`：**不允许编造**——转第 3 步第 4 类红线。
- 若未配置 `IMA_HR_KNOWLEDGE_BASE_ID`，脚本会按名称偏好匹配含「政策/HR/人事…」的知识库；不合适时先 `--list-kb` 再让人工配置 ID。

### 第 2 步 · 基于检索结果答复，并引用出处

- 答复内容**只能来自** `highlight` / `content_excerpt` 与 `title`。用员工能听懂的话转述，但**关键数字必须与片段逐字一致**。
- 每条答复**必须在结尾注明政策出处**，格式优先：`政策依据：《04-薪酬与社保公积金》`（从 `title` 映射；多份则全部列出）。
- 答复结构：先给结论，再给细节，不堆砌无关条款。
- 若片段仍不足以覆盖关键点，对不确定数字**不要补全**，引导人工 HR。

### 第 3 步 · 红线问题升级人工（HiTL）

回答之前先判断：员工问的是「政策怎么规定」，还是「我的个案/我的数据/我的法律处境」？前者答，后者升级。

遇到以下 5 类情形，**不要自行作答**，明确转人工并说明原因：

1. **涉及个人具体金额/数据**——需要查个人考勤、薪资、社保、个税、年假余额。你没有也不该有这个数据访问权限。
2. **个案争议**——对绩效结果、扣款、处分、安排表示不服或异议。
3. **法律纠纷/劳动仲裁**——对个案法律定性、经济补偿争议、工伤认定、劳动仲裁。
4. **知识库无依据**——IMA `search_ima_policies` 无命中，或明显超出政策库覆盖范围。不许用通用知识硬答。
5. **需要决策审批**——特殊安排、破例处理，需人工 HR 决策。

细则见 → `references/escalation-redlines.md`

## 关键规则（这几条必须守死）

- **检索得到 ≠ 该回答。** 判断「该不该答」必须先于「能不能检索到」。
- **红线问题不是「答得小心一点」，是不答、明确转人工。**
- **政策里的数字一字不能改。**
- **升级不是甩一句「请联系人工」。** 政策能答的部分照常答，说明升级原因与人工渠道。
- 即使员工提到「劳动仲裁」，也不对个案下合法/赔偿结论。
- **禁止**改用 `memory_search` 回答政策问题（本 Skill 已切换为 IMA）。

## 这个 Skill 不做什么

- 不查询任何员工的个人数据——第 1 类红线。
- 不做会议纪要、不生成月报。
- 不在答疑流程里上传/改写 IMA 知识库（入库是运维一次性操作）。
