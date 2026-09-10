# 入职进度看板规格

> `generating-onboarding-dashboard` Skill 的看板内容细则。SKILL.md 正文是工作流，本文件是「看板每一格是什么意思」的细则。SKILL.md 在需要时引用本文件。

## 目录

- 1. 看板汇总的 5 个准备节点 + 试用期跟进 + 流程角标
- 2. 节点状态怎么归类
- 3. 整体进度怎么算
- 4. 数据从哪来
- 5. 花名册来源与边界情况
- 6. 发布到 Canvas

## 1. 看板汇总的 5 个准备节点 + 试用期跟进 + 流程角标

每名新员工一张卡片：右上角 **流程角标** + **入职准备 5 节点** + **试用期 7/30/60/90**。跟进来自 HR 本地表，不进 HCM。

**流程角标（主角标，读 HCM 5 个准备节点）**：

| 5 节点 | 角标 |
|---|---|
| 全部 done（含 `data.status` 已审批/已通过等） | 已完成 5/5 |
| 有进展也有未完成 | 入职中 n/5 |
| 全部 pending | 待启动 0/5 |

**审批门标记（单独一枚，读 `workflow.json`）**：halted 显示门名称 + 停留天数；满 3 天加「请催办」。cancelled 显示「审批已取消」。workflow `completed` **不再**把主角标打成「已完成」——那只表示审批走完，不代表人已到岗。

**入职准备 · 5 节点**（HCM `GET /api/candidates` 的 `nodes[]`）：顶层 `status=completed` 以状态机为准；仅当顶层尚未 completed 时，才用部门中文 `data.status`（如「已审批」）提前标绿。

| 节点 | 含义 | 真相源 |
|---|---|---|
| 合同签署 | 劳动合同审批与签署 | HCM `node_type=contract` |
| IT 账号 | 邮箱、办公系统账号开通 | HCM `node_type=account` |
| 行政设备 | 电脑、工位等设备配齐 | HCM `node_type=device` |
| Buddy 匹配 | 入职伙伴 / 导师匹配 | HCM `node_type=buddy` |
| 入职培训 | 入职培训排期 | HCM `node_type=training` |

**试用期跟进 · 4 节点**（本机 `review-state/reviews.json`）：

| 显示 | 含义 |
|---|---|
| 未开通 | 尚未 `armed`（五节点未全绿或未挂 Cron） |
| 未到点 | `pending`，Cron 还没催 |
| 待回填 | `due`（Cron 已催） |
| 逾期未回填 | `due` 且 `triggered_at` 已过上海时区自然日（派生，不落库） |
| 正常 / 关注 / 风险 / 跳过 | CLI `record --outcome` 后的结论 |

本机 `stub-state/<pinyin>/` 里的合同/账号等 JSON **不是**看板准备节点的真相源；看板只拿该目录下的 `workflow.json` 做审批门角标。

## 2. 节点状态怎么归类

HCM 节点文案归到 3 个标准态：

- **done（已完成）** —— 「已审批 / 已通过 / 已开通 / 已配齐 / 已匹配 / 已完成 / 已签署 / 已排期」或顶层 `completed`。绿色。
  - 「已排期」也算 done——培训排好日期即办妥。
  - 「已通过」与「已审批」同义，均表示 HiTL 门已批过。
- **pending（待办）** —— 「待审批 / 待办 / 待制 / 待分配 / 待排期 / 待开通 / 未就绪」，或以「待」字开头。灰色。
  - 「待审批」= 已进审批门、等真人批（与角标 `halted` 对应）。
- **progress（进行中）** —— 不属于上面两类的（如「起草中」）。橙色。

## 3. 整体进度怎么算

```
整体进度 % = 准备节点 done 数 / 5 × 100
```

试用期回填**不计入**整体进度百分比。进度条：≥80% 绿、50%-79% 橙、<50% 红。顶部「平均进度」= 所有员工整体进度的算术平均。

整体进度**不**把 workflow 角标单独计入——角标是定性提示（卡在哪扇门），进度条按 5 个准备节点 done 占比。

## 4. 数据从哪来

| 来源 | 谁写的 | 看板读什么 |
|---|---|---|
| HCM `GET /api/candidates` | 各部门在 HCM 填写 | 花名册、5 个准备节点 |
| `stub-state/<pinyin>/workflow.json` | `update-workflow.py`（lobster 各节点调用） | 审批门角标（status / current_step） |
| `review-state/reviews.json` | `review-store.sh` / Cron 催办 | 7/30/60/90 状态与结论 |

脚本靠 `HCM_API_URL` / `HCM_API_BASE`（默认 `http://localhost:8000`）和 `ONBOARDING_WORKSPACE` 定位。HCM 不可达时直接退出，不拿本地 stub 冒充准备节点。跟进表缺失时按「未开通」显示，不退出。

## 5. 花名册来源与边界情况

**花名册**：HCM 返回的候选人列表，不是扫描 `stub-state*`。

**边界情况**：

- HCM 节点缺失 → 显示「未就绪」，卡片照常生成。
- 无 `workflow.json` → 无审批门角标，准备节点仍展示。
- HCM 无候选人 / API 失败 → 退出（API 失败 exit 5）。
- 准备节点已绿但角标仍 `halted` → 正常：材料已备、审批未过。
- 跟进未 `armed` → **不画四格空节点**，只留「试用期跟进 · 未开通」和「入职准备还没办完，试用期跟进还没开始」。开通条件是五部门准备节点都完成；审批取消只显示在角标，不改写跟进原因。

## 6. 发布到 Canvas

生成 HTML 后，用 `publish_to_canvas.py`（或 `build-dashboard.sh --publish`）复制到 OpenClaw Canvas host：

| 项 | 约定 |
|---|---|
| canvas-id | 固定 `onboarding-dashboard`（ASCII） |
| 落盘 | `$OPENCLAW_STATE_DIR/canvas/documents/onboarding-dashboard/index.html` |
| 查看 | `http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html` |
| 覆盖 | 同名已存在需 `--force` |

约束细则与踩坑见 → `canvas-publishing.md`。
