---
name: running-onboarding-workflow
description: Run the new-hire onboarding approval workflow for a single employee using the Lobster workflow engine. Use this skill whenever a new hire needs to go through onboarding — it drives 4 parallel preparation tracks (contract, IT account, equipment, training) and 2 human-in-the-loop approval gates (contract approval, account-permission approval). Handles the full lifecycle: start the workflow, hand back the resumeToken when it halts at an approval gate, and resume with approve or reject. The agent never approves on a human's behalf.
metadata:
  openclaw:
    requires:
      bins: ["node", "bash", "python3"]
---

# running-onboarding-workflow

用 Lobster 工作流引擎，跑一名新员工的入职审批流程。

## 这个 Skill 封装的是一条工作流，不是一个脚本

入职审批是一条多步、多审批门、有状态的流程：4 路并行准备 + 2 个 HiTL（人在回路）审批门。它的流程定义写在一个 Lobster 工作流文件 `scripts/hr-onboarding.lobster` 里。这个 Skill 做的事是告诉你**何时发起这条工作流、怎么用 lobster 跑、流程在审批门暂停后怎么接管**——工作流文件是"流程定义"，这个 Skill 是"操作手册"。

发起和接管工作流的 lobster 调用细节（CLI 入口、文件路径、参数传法、环境变量注入）已经固化进启动脚本 `scripts/run-onboarding.sh`，你只需照下面三条命令调用，不要自己拼 lobster 命令。

## 何时用这个 Skill

一名新员工确定录用、要走入职流程时用。典型触发：「为新员工 X 启动入职」「X 的入职审批走一下」「HR 主管批准了 X 的合同，继续推进」。

## 前置条件 · HCM 花名册先行（强制）

**HCM 是花名册与五部门节点的唯一写入面。小慧 / 本 Skill 不向 HCM 做 POST/PUT。**

启动前必须已在 HCM 建档（看板「新增」或 `POST /api/candidates`，拼音与 `start` 参数一致）。`run-onboarding.sh start|dry` 会 **GET** `$HCM_API_BASE/api/candidates`（默认 `http://127.0.0.1:8000`）按拼音精确匹配：

- **查不到或 HCM 不可达** → 退出非 0，提示先建档；**不**清 stub、**不**调 lobster。
- **查到** → 只写本机 `stub-state/<pinyin>/`，跑审批工作流。

SOP：先 HCM 建人 → 再对小惠说「启动某某入职」。

## 数据读写边界

- **花名册校验**：启动前 GET HCM 确认拼音存在，不写 HCM。
- **准备节点数据**：各准备脚本从 HCM 读取部门填写的数据（只读），同时写本地 `stub-state/<pinyin>/` 供审批 prompt 生成。
- **审批门 / resumeToken**：HCM 无此概念，由 Lobster 工作流落盘到 `workflow.json`。
- **看板**：从 HCM API 读取（只读），不读本地 stub-state 作为准备节点真相源。

## 工作流程

入职审批工作流有三个动作：启动、批准/拒绝一个审批门、查看计划。都通过启动脚本调用。

### 第 1 步 · 启动工作流

```bash
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>
```

例：`run-onboarding.sh start 张磊 zhanglei 后端工程师 32K`。拼音用于生成邮箱前缀（中文进 `tr` 会被破坏，所以单独传拼音），且必须已在 HCM 花名册中。

启动后，4 路并行准备（合同 / IT 账号 / 设备 / 培训）会跑完，流程在**第一个审批门 `contract_gate` 暂停**，返回一段 JSON。JSON 里 `status` 是 `needs_approval`，`requiresApproval` 块里有四样东西，你必须把它们清楚交回给人：

- `prompt` —— 审批问题（已含候选人专属信息 + 状态 + 时间戳）。**这是给人看的唯一正文，必须原样展示，禁止删改、禁止用自己画的表格替代。**
- `items` —— 待审原始 JSON，仅作核对/存档；**不要自己从 items 挑字段重画「项目|内容」表**——容易漏掉 `status` 等核心字段，也容易给空字段硬加一行。
- **`resumeToken`** —— 恢复流程的钥匙。**这是后续 resume 必须用的字段，务必原样留存并交回。** 不要只交回 `approvalId`——`approvalId` 只是个短标识，resume 不认它。
- `approvalId` —— 审批请求的短标识，仅供人引用。

### 交回审批内容时的展示规则（强制）

`run-onboarding.sh` / 查询 Skill 会在 stderr 打印 `---PROMPT---` 等标记块。

1. **PROMPT 内核一字不改**（标记之间的正文）。
2. **对用户隐藏机器标记行**（`=====`、`---PROMPT---`、`[display-hint]` 等不要出现在回复里）。
3. 推荐排版：开头用 2～4 条短状态列表 → `### 待你审批` 下用引用块贴 PROMPT → `### 恢复钥匙` 下用代码块贴 token。
4. **禁止** emoji 自造表、禁止编造「内网访问」等字段、禁止用四件套清单顶替当前门正文。

示例结构（PROMPT 处必须是脚本原文）：

```markdown
## 小豆豆入职进度

- 流程状态：待审批（已暂停）
- 当前节点：账号权限审批门（account_gate）

### 待你审批

> IT 安全负责人，请审批 …（整段原样）

### 恢复钥匙（resumeToken）

\`\`\`
eyJ...
\`\`\`

请回复「批准」或「拒绝」。
```


### 第 2 步 · 批准或拒绝审批门

人做出决定后，用上一步返回的 `resumeToken` 推进：

```bash
# 批准
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh resume <resumeToken> yes
# 拒绝
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh resume <resumeToken> no
```

- **批准合同门**后，流程推进到第二个审批门 `account_gate`（账号权限审批），再次 `needs_approval`。**每次 halt 都生成一个新的 resumeToken**——第二次 resume 必须用第二步返回的新 token，不能用第一步的旧 token。
- **两个审批门都批准**后，`status` 变 `ok`，`buddy`（带教导师匹配）和 `complete`（归档）节点执行，入职五项就绪。
- **任一审批门被拒绝**，`status` 变 `cancelled`，`buddy` / `complete` 节点不执行。如实报告流程已终止。

### 第 3 步（可选）· 先看执行计划

不确定工作流会跑什么时，可以先 dry-run，只打印执行计划、不真正执行：

```bash
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh dry <姓名> <拼音> <岗位> <薪资>
```

## 关键规则

- **审批门是给人的，不是给你的。** 流程在 `contract_gate` / `account_gate` 暂停时，你的职责是把 `prompt` + `resumeToken` 交回给人，等人做决定。**绝不替人批准或拒绝。**
- **PROMPT 内核原样交回，标记行对用户隐藏。** 见到 `---PROMPT---` 必须粘贴其间正文；不要把 `=====` / `---PROMPT---` / `[display-hint]` 念给用户听。可用 Markdown 外壳美化，禁止改内核、禁止 emoji 表、禁止编造「内网访问」。
- **resumeToken 必须原样留存。** 每次 halt 返回的 token 是流程状态的唯一钥匙，丢了就接不回流程。每个门一个新 token。
- **启动前不要手动跑 stub 脚本。** `start` 会自己清掉旧状态、跑 4 路并行准备。重复跑会污染状态文件。
- **不要替 HCM 建档或改部门节点。** 花名册与五部门写入只在 HCM；本 Skill 只读校验拼音是否存在。
- 入职审批工作流的设计依据、4 路并行 / 双审批门为什么这么设计，见 → `references/workflow-design.md`。
