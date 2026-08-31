---
name: querying-onboarding-status
description: 查询入职审批工作流当前状态——按候选人全名查 workflow.json / pending-approvals/，对比 halt 时 vs 当前 stub，并输出强制原样交回的 PROMPT 标记块。
---

# querying-onboarding-status · 入职审批状态查询 Skill

## 用途

HR 在工作流 halt 之后不确定"现在该不该 resume"时，用本 Skill 一键查进度与待审正文。

## 用法

```bash
scripts/query-onboarding-status.sh 员工1
# 或显式拼音：
scripts/query-onboarding-status.sh 员工1 yuangong1
```

拼音可省：会先查内置表，再扫 `stub-state/*/workflow.json` 的 `candidate` 字段自动匹配。

**必须跑本 Skill 脚本**（不要只 `cat` workflow/json）。脚本会按当前门重跑对应 shell 刷新落盘，再拼 PROMPT。

## ⚠ 交回用户时的硬规则

stderr 会有机器标记块（`---PROMPT---` … `---END_PROMPT---` 等）。

### 必须做到

1. **PROMPT 正文一字不改**（`---PROMPT---` 与 `---END_PROMPT---` 之间的内容）。
2. **RESUME_TOKEN 一字不改**，放进 markdown 代码块方便复制。
3. **隐藏所有机器标记行**（`=====`、`---STATUS---`、`---PROMPT---`、`[display-hint]` 等）——用户不应看到这些标记。
4. **禁止**把 PROMPT 改写成 emoji 表；**禁止**编造「内网访问」等字段。

### 推荐展示模板（外壳可美化，PROMPT 内核禁止改）

```markdown
## {候选人}入职进度

- 流程状态：{STATUS 里的流程状态}
- 当前节点：{STATUS 里的当前节点}
- 暂停于：{若有}

### 待你审批

> （此处粘贴 ---PROMPT--- 与 ---END_PROMPT--- 之间的全文，保持换行；
>  可用引用块，但不得增删改任何字）

### 恢复钥匙（resumeToken）

\`\`\`
{RESUME_TOKEN 全文}
\`\`\`

请回复「批准」或「拒绝」。
```

## 工程契约

1. PROMPT 唯一真源：`build-approval-prompt.py`（拼之前必先 `refresh-gate-stubs.py` 重跑对应门 shell）。
2. account 门含 account + device + training；contract 门含 status；files 仅在有数据时出现。
3. 查流程时：先按当前门刷新落盘，再读 JSON 投影 prompt，保证 HR 决策依据是最新物料。
