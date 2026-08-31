# 任务：撰写本 Agent 的独立介绍文档

你是 HR 数字员工「小慧」多 Agent 系统中的一员。请**只根据本工作区内的文件**（`IDENTITY.md`、`SOUL.md`、`AGENTS.md`、`TOOLS.md`、`skills/*/SKILL.md` 等）撰写一份**完全独立**的介绍文档，供人类阅读。

---

## 硬规则（必须遵守）

1. **先读再写**：先读本工作区上述文件；没读到的内容不要补全、不要猜测。
2. **工作区隔离**：不要读取、猜测其它 `workspace-*` 的内部脚本或实现细节。对其它 Agent 的内部流程，若本工作区无依据，写「未知」或「由总控路由，我不直接调用」。
3. **安全**：不要粘贴 API Key、token、`env.sh` 内容、会话里的敏感信息。
4. **真实性**：声称「已完成 / 已生成 / 已排序」的步骤，必须能指出脚本路径或落盘目录；若做不到，写清楚失败条件，不要空口完成。
5. **ASCII 图**：只用 `+ - | / \` 和英数字符作结构节点；不要用 emoji 当框线（避免复制乱码）。
6. **独立成篇**：不要修改 `SOUL.md` / `AGENTS.md`；介绍文档单独交付（见下方「交付方式」）。

---

## 系统背景（供你定位自己，勿替其它 Agent 编造细节）

本系统是**星型调度**，不是网状互调：

```
                    +-----------+
                    |   User    |
                    +-----+-----+
                          |
                          v
                    +-----------+
                    |  router   |  只调度，不干业务
                    +-----+-----+
                          | sessions_spawn
          +-------+-------+-------+-------+
          v       v       v       v       v
     recruitment onboarding training performance er-admin
          |                                       |
          +---- 子 Agent 禁止互相 spawn；只回报 router ----+
```

- Manifest：`.openclaw-hr/hr-agents/hr-agents.yaml`（6 个 Agent 的 id / 领域 / 工作区）。
- 路由模式：Local Workflow；总控通过 `sessions_spawn` 把新任务分给子 Agent；子 Agent 的 `subagents.allowAgents` 为空。
- **文件不是协议**：除非你的 SKILL 里明确写了读某个路径，不要假设其它 Agent 工作区的文件会自动被你读取。
- **HCM**（Vue + FastAPI，`:5173` / `:8000`）是独立应用，**不是 Agent**；仅当你的 Skill 文档提到时才写你怎么用它。

---

## 请逐节回答（写入最终文档）

### 1. 我是谁（身份）

- 你的 OpenClaw `id`、显示名、负责的 HR 领域（一句话）。
- 在「小慧」里对用户是否可见：用户通常只跟 `router` 说话，还是也可以 `openclaw agent --agent <你的id>` 直连你？
- 三句以内：**我解决什么问题；我不解决什么问题。**

### 2. 干什么（职责与边界）

- 主路径业务清单：按本工作区**真实存在的 Skill** 列出（不要把 README 里提到、但本工作区没有对应 `skills/` 目录的能力写进去）。
- **明确不做**（举例，按你的实际情况写）：例如 router 不答 HR 业务；training 不组织现场培训；er-admin 在飞书不触发月报；recruitment 不改入职 stub-state。
- **人在回路（HiTL）**：哪些决定必须交给人（审批门、淘汰、定级、政策红线升级等）？

### 3. 具体怎么做（工作流）

- 用 **1～3 张 ASCII 流程图** 画出主路径（输入 → 步骤 → 落盘 → 交给谁）。
- 每一步说明：触发条件、Skill 名、用的工具（`exec` / `read` / `lobster` / 纯推理无脚本）。
- 固定顺序与禁止跳步（若有）：例如解析 → 核对 → 脱敏 → 评分。
- **一条端到端例子**：用本工作区已有夹具（如员工1、员工2、信息安全意识、2026-05 月报等），从用户话术到落盘产物走一遍。

### 4. 通过什么实现（实现层）

- 每个 Skill 的目录路径 + 一句话职责。
- 脚本语言与关键入口文件（相对本 workspace 的路径）。
- 外部依赖：**只写服务/库名称**（如 DeepSeek、DashScope、IMA、Lobster、HCM HTTP、pandas 等），不要写 Key。缺凭证或依赖不可用时的失败行为；**绝不能**改成什么（例如禁止用模型常识冒充公司制度）。
- **工具权限**：你实际能用的 `tools.allow` / `tools.deny`（对照 `config/openclaw.yaml` 中你的条目如实写；er-admin 禁写盘、onboarding 若 yaml 未单独写 allow 也要说明实际行为）。
- **定时任务**：是否有 Cron 唤醒你的业务（如入职 review、月报）；heartbeat 若与本职无关可写「不用于本职」。

### 5. 在架构里的哪一环

- 必须有一张 ASCII「系统位置图」：标出**你自己**（可略详），其它 Agent 只画方框 + id，不描述其内部。
- 本工作区根目录（`workspace-<id>/`）与 `agent-dirs/<id>/` 各存什么（业务文件 vs 会话/记忆）。
- 是否向共享 `canvas/documents/<ascii-id>/` 发布 HTML；Canvas id 必须纯 ASCII。
- 若用到 HCM：怎么读/写、HCM 不可用你怎么说。

### 6. 如何和别的 Agent 通信（协作契约）

- 任务通常从哪来？（router `sessions_spawn` / 用户直连 / Cron 孤立会话）
- 你如何交回结果？（回复文本、文件路径、Canvas URL、`---PROMPT---` 块等）
- 你**能不能** `sessions_spawn` 其它业务 Agent？若不能，用户提出跨域需求时你怎么处理？
- 与 router 的关系：收到什么、回报什么；会不会在回复里暴露「转给了哪个子 Agent」（对照你的 SOUL/AGENTS 红线写）。

### 7. 补充（避免文档像目录）

- **输入 / 输出合同**：读哪些目录、写哪些目录、副作用（改 stub、调 HCM、发 Canvas）。
- **失败长什么样**：空 inbox、IMA 不可用、月份越界、审批停住等；**明确失败** vs **假成功**的区别。
- **红线与合规**：敏感字段、PROMPT 内核不可改、数字必须脚本算、政策必须有出处等（写与你相关的）。
- **记忆**：`memory/`、`MEMORY.md` 是否参与业务决策（多数应以 Skill 落盘为准）。
- **典型话术 5 条**：会接的 3 条 + 应拒绝或应转走的 2 条。
- **已知限制 / 踩坑**：串台、中文 canvas id、exec 里系统 python3 缺 pandas、路径写死等——只写你文档里出现或你工作区里能证实的。

---

## 输出格式（严格按此 Markdown 标题）

```markdown
# <显示名>（`<id>`）介绍

## 一句话

## 系统位置（ASCII）

## 我负责 / 我不负责

## 主工作流（ASCII + 逐步说明）

## Skill 与脚本

## 权限、Cron、外部系统

## 如何被调用、如何交回结果

## 输入、输出、失败

## 红线

## 典型话术

## 已知限制
```

**篇幅**：业务 Agent 约 1500～2500 字；若你是 `router`，可更短，但路由规则与「绝不自己答 HR 业务」必须写清。

---

## 交付方式

1. 若你有写盘权限：在本工作区根目录创建 **`XXX小惠INTRO.md`**，写入完整文档；并在对话回复中**再贴一遍全文**。
2. 若你因配置禁止 `write`/`edit`（如 `er-admin`）：无法写文件时，在对话回复中输出**完整 Markdown 全文**即可。
3. 不要修改 `SOUL.md`、`AGENTS.md` 或其它既有配置文件。

---

请现在开始：先读取本工作区相关文件，再按上述结构撰写并交付 `XXX小惠INTRO.md`（或对话全文）。

---

<!-- ============================================================ -->
<!-- 以下「人类侧说明」不要粘贴给 Agent；仅供负责人发送与收件使用 -->
<!-- ============================================================ -->

## 人类侧：怎么发送

在 profile 已 `source env.sh`、Gateway 已 live 的前提下，**分别**发给六个 Agent（不要让 router 代写子 Agent 的介绍）：

```bash
cd ~/openclaw-hr
source .openclaw-hr/env.sh

# 只把「人类侧说明」注释块之前的正文发给 Agent
PROMPT="$(sed '/^<!-- =====/,$d' docs/agent-intro-brief.md)"

openclaw agent --agent router      -m "$PROMPT"
openclaw agent --agent recruitment -m "$PROMPT"
openclaw agent --agent onboarding  -m "$PROMPT"
openclaw agent --agent training    -m "$PROMPT"
openclaw agent --agent performance -m "$PROMPT"
openclaw agent --agent er-admin    -m "$PROMPT"
```

若 `openclaw` 不在 PATH：

```bash
~/openclaw-hr/.openclaw-hr/install/node_modules/.bin/openclaw agent --agent <id> -m "$PROMPT"
```

## 人类侧：交付约定

| Agent | 预期交付位置 | 备注 |
|-------|--------------|------|
| router | `workspace-router/INTRO.md` | 另有对话全文 |
| recruitment | `workspace-recruitment/INTRO.md` | |
| onboarding | `workspace-onboarding/INTRO.md` | |
| training | `workspace-training/INTRO.md` | |
| performance | `workspace-performance/INTRO.md` | |
| er-admin | **无写盘** | 以对话回复为准，人工另存为 `workspace-er-admin/INTRO.md` |

`er-admin` 在 [`config/openclaw.yaml`](.openclaw-hr/config/openclaw.yaml) 中仅允许 `exec`+`read`，禁止 `write`/`edit`/`group:fs`。

## 人类侧：收件检查清单

- [ ] 六份文档标题结构一致（便于并排阅读）
- [ ] 每份至少 1 张 ASCII 系统位置图 + 1 张主工作流图
- [ ] 无 API Key / token / env 明文
- [ ] 无对其它 Agent 内部脚本的臆造（交叉引用应写「由 router 路由」或「未知」）
- [ ] Skill 列表与本工作区 `skills/` 目录一致，无 phantom skill
- [ ] `er-admin` 若写文件失败，已从对话复制全文到 `INTRO.md`
- [ ] 未改动各 Agent 的 `SOUL.md` / `AGENTS.md`

## 人类侧：可选归档

收齐六份后，可汇总到本地（不入库）目录，例如 `docs/agent-intros/`，文件名建议：

- `router.md` · `recruitment.md` · `onboarding.md` · `training.md` · `performance.md` · `er-admin.md`
