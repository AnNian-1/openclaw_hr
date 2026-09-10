---
name: running-onboarding-workflow
description: Run the new-hire onboarding approval workflow for a single employee using the Lobster workflow engine. Snapshots HCM department nodes (read-only; never fills in for other departments), then drives 2 human-in-the-loop approval gates (contract, account-permission). Probation 7/30/60/90 reviews are armed only when all 5 HCM nodes are completed. Handles start, halt/resumeToken, and resume. The agent never approves on a human's behalf.
metadata:
  openclaw:
    requires:
      bins: ["node", "bash", "python3"]
---

# running-onboarding-workflow

用 Lobster 工作流引擎，跑一名新员工的入职审批流程。

## 这个 Skill 封装的是一条工作流，不是一个脚本

入职审批是一条多步、多审批门、有状态的流程：从 HCM **只读快照**五部门节点 + 2 个 HiTL 审批门。它的流程定义写在 `scripts/hr-onboarding.lobster`。这个 Skill 告诉你**何时发起、怎么用 lobster 跑、审批门暂停后怎么接管**。

入职小慧**不代替**合同/IT/行政/培训/Buddy 部门在 HCM 里填节点，不编造「劳动合同已起草 / 设备已配齐 / 培训已排期 / Buddy 王工」。进度以 HCM `nodes[].status` 为准；未完成就催对应部门。

发起和接管的 lobster 细节已固化进 `scripts/run-onboarding.sh`，照下面命令调用，不要自己拼 lobster。

## 何时用这个 Skill

一名新员工确定录用、要走入职流程时用。典型触发：「为新员工 X 启动入职」「X 的入职审批走一下」「HR 主管批准了 X 的合同，继续推进」。

## 前置条件 · HCM 花名册先行（强制）

**HCM 是花名册与五部门节点的唯一写入面。小慧 / 本 Skill 不向 HCM 做 POST/PUT。**

启动前必须已在 HCM 建档（看板「新增」或 `POST /api/candidates`，拼音与 `start` 参数一致）。`run-onboarding.sh start|dry` 会 **GET** `$HCM_API_BASE/api/candidates`（默认 `http://127.0.0.1:8000`）按拼音精确匹配：

- **查不到或 HCM 不可达** → 退出非 0，提示先建档；**不**清 stub、**不**调 lobster。
- **查到** → 只写本机 `stub-state/<pinyin>/`，跑审批工作流。

SOP：先 HCM 建人 → 再对小惠说「启动某某入职」。

## 数据读写边界

| 数据 | 真相源 | 小慧 |
|------|--------|------|
| 花名册 + 五部门节点 | HCM GET only | 只读快照、催办；**禁止 POST/PUT** |
| 审批门 / resumeToken | 本机 `stub-state/<pinyin>/workflow.json` | 启动/resume Lobster |
| 试用期 7/30/60/90 | 本机 `review-state/reviews.json` | **仅当五节点均为 `completed`** 才 ensure + 挂 Cron |

- **进合同审批门**：HCM 合同节点须为 `in_progress` 或 `completed`，否则 `start` 退出 **6**，`workflow.json` 记 `waiting_departments`，不跑 lobster。
- **开通试用期跟进**：五节点都必须是 `completed`。两道审批门都批过（lobster `complete`）**不等于**部门已执行完毕。
- **看板**：准备节点读 HCM；review 读本地表；审批角标读 `workflow.json`。

## 工作流程

入职审批工作流有三个动作：启动、批准/拒绝一个审批门、查看计划。都通过启动脚本调用。

### 第 1 步 · 启动工作流

```bash
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>
```

例：`run-onboarding.sh start 员工1 yuangong1 后端工程师 32K`。拼音用于生成邮箱前缀（中文进 `tr` 会被破坏，所以单独传拼音），且必须已在 HCM 花名册中。

启动后，prep **只快照 HCM**（不编造部门产出）。合同节点已开始/完成后，流程在**第一个审批门 `contract_gate` 暂停**，返回 JSON。`status` 是 `needs_approval`，`requiresApproval` 里有四样东西，必须交回给人：

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
## 员工1入职进度

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

- **批准合同门**后，流程推进到第二个审批门 `account_gate`。**每次 halt 都生成新 resumeToken**。
- 账号门 prompt 会带上 HCM 真实状态。若账号/设备/培训仍为 `pending`，**不要建议批准**，先催对应部门在 HCM 填写。
- **两个审批门都批准**后，`status` 变 `ok`，归档。**此时不要宣称试用期跟进已挂上**——须五节点全绿后 `sync-reviews-if-ready.sh` 才会 ensure + 注册 Cron。
- **任一审批门被拒绝**，`status` 变 `cancelled`。如实报告。
- 合同尚未开始时 `start` 退出 6：报告「等待部门填写」，催 HR 在 HCM 操作后再 `start`。不要 resume。

### 第 3 步（可选）· 先看执行计划

不确定工作流会跑什么时，可以先 dry-run，只打印执行计划、不真正执行：

```bash
bash skills/running-onboarding-workflow/scripts/run-onboarding.sh dry <姓名> <拼音> <岗位> <薪资>
```

## 关键规则

- **审批门是给人的，不是给你的。** 绝不替人批准或拒绝。材料在 HCM 仍为 pending 时，交回 prompt 并说明请勿批准。
- **PROMPT 内核原样交回，标记行对用户隐藏。**
- **resumeToken 必须原样留存。** 每个门一个新 token。
- **不要替部门执行。** 禁止编造合同/工号/设备/培训/Buddy。未完成就催办。
- **不要替 HCM 建档或改部门节点。** 只读校验拼音是否存在。
- **启动前不要手动跑快照脚本。** `start` 会清旧状态再快照 HCM。`waiting_departments` 允许再次 start；`halted`/`completed` 须 `--force`。
- **halt ≥ 3 天只催办，不自动 resume。**
- resume 前启动器会打印两门当下 prompt 预览（非陈旧快照）；halt 返回的 token 回填 `pending-approvals/`。
- 设计依据见 → `references/workflow-design.md`。
