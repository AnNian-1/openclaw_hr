# 入职进度看板规格

> `generating-onboarding-dashboard` Skill 的看板内容细则。SKILL.md 正文是工作流，本文件是「看板每一格是什么意思」的细则。SKILL.md 在需要时引用本文件。

## 目录

- 1. 看板汇总的 9 个节点 + 流程角标
- 2. 节点状态怎么归类
- 3. 整体进度怎么算
- 4. 数据从哪来
- 5. 自动发现机制与边界情况
- 6. 发布到 Canvas

## 1. 看板汇总的 9 个节点 + 流程角标

每名新员工一张卡片：右上角 **流程角标** + 两段共 9 个节点。

**流程角标**（读自同目录 `workflow.json`）：

| `status` | 角标示意 |
|---|---|
| `halted` | 等待审批 · 合同审批门 / 账号审批门 |
| `started` | 进行中 · 当前步骤 |
| `completed` | 已完成 |
| `cancelled` | 已取消 |
| 无文件 | 无流程记录 |

准备节点全绿但角标仍是「等待审批」，说明 stub 已备好、真人还没批——以角标为准。

**入职准备 · 5 节点**（对应入职审批工作流的 5 个 stub 系统）：

| 节点 | 含义 | 数据文件 |
|---|---|---|
| 合同签署 | 劳动合同审批与签署 | `stub-state/<pinyin>/contract.json` |
| IT 账号 | 邮箱、办公系统账号开通 | `stub-state/<pinyin>/account.json` |
| 行政设备 | 电脑、工位等设备配齐 | `stub-state/<pinyin>/device.json` |
| Buddy 匹配 | 入职伙伴 / 导师匹配 | `stub-state/<pinyin>/buddy.json` |
| 入职培训 | 入职培训排期 | `stub-state/<pinyin>/training.json` |

（旧结构 `stub-state-<姓名>/` 下文件名相同。）

**试用期跟进 · 4 个 review 节点**：

| 节点 | 含义 | 数据文件 |
|---|---|---|
| 第 7 天 | 报到第一周跟进 | `review-state/review-<姓名>-day7.json` |
| 第 30 天 | 入职第一个月跟进 | `review-state/review-<姓名>-day30.json` |
| 第 60 天 | 入职第二个月跟进 | `review-state/review-<姓名>-day60.json` |
| 第 90 天 | 入职第三个月跟进 | `review-state/review-<姓名>-day90.json` |

## 2. 节点状态怎么归类

`stub-state*` 里的准备节点状态文案归到 3 个标准态：

- **done（已完成）** —— 「已审批 / 已通过 / 已开通 / 已配齐 / 已匹配 / 已完成 / 已签署 / 已排期」。绿色。
  - 「已排期」也算 done——培训排好日期即办妥。
  - 「已通过」与「已审批」同义，均表示 HiTL 门已批过。
- **pending（待办）** —— 「待审批 / 待办 / 待制 / 待分配 / 待排期 / 待开通 / 未就绪」，或以「待」字开头。灰色。
  - 「待审批」= 已进审批门、等真人批（与角标 `halted` 对应）。
- **progress（进行中）** —— 不属于上面两类的（如「起草中」）。橙色。

review 4 节点：对应 JSON 存在 = 「已 review」（done），不存在 = 「待触发」（pending）。

## 3. 整体进度怎么算

```
整体进度 % = (准备节点 done 数 + review 节点 done 数) / 9 × 100
```

进度条：≥80% 绿、50%-79% 橙、<50% 红。顶部「平均进度」= 所有员工整体进度的算术平均。

整体进度**不**把 workflow 角标单独计入——角标是定性提示（卡在哪扇门），进度条仍按 9 节点 done 占比。

## 4. 数据从哪来

| 目录 / 文件 | 谁写的 | 看板读什么 |
|---|---|---|
| `stub-state/<pinyin>/`（或旧 `stub-state-*`）| `running-onboarding-workflow` | 5 个准备节点、姓名 / 岗位 |
| 同目录 `workflow.json` | `update-workflow.py`（lobster 各节点调用）| 流程角标（status / current_step）|
| `review-state/` | `running-onboarding-review` | 4 个 review 是否已 review |

脚本靠 `ONBOARDING_WORKSPACE` 或「自身位置向上三级」定位 workspace 根。

## 5. 自动发现机制与边界情况

**自动发现**：扫描所有以 `stub-state` 开头的目录。

- 新结构：`stub-state/<pinyin>/` 每个有效子目录一名员工。
- 旧结构：无子目录时，目录本身一名员工。
- **有效目录**：至少存在 `contract.json` 或 `workflow.json`（空壳跳过）。
- **同名去重**：优先保留 `stub-state/<pinyin>/`。

姓名优先 `contract.json.candidate`，其次 `workflow.json.candidate`，再目录名兜底。

**边界情况**：

- 缺部分节点 JSON → 显示「未就绪」，卡片照常生成。
- 无任何 review → 4 个节点全「待触发」。
- 无任何有效 `stub-state*` → 退出码 2，「还没有员工跑过入职工作流」。
- 准备节点已绿但角标仍 `halted` → 正常：材料已备、审批未过。

## 6. 发布到 Canvas

生成 HTML 后，用 `publish_to_canvas.py`（或 `build-dashboard.sh --publish`）复制到 OpenClaw Canvas host：

| 项 | 约定 |
|---|---|
| canvas-id | 固定 `onboarding-dashboard`（ASCII） |
| 落盘 | `$OPENCLAW_STATE_DIR/canvas/documents/onboarding-dashboard/index.html` |
| 查看 | `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html` |
| 覆盖 | 同名已存在需 `--force` |

约束细则与踩坑见 → `canvas-publishing.md`。
