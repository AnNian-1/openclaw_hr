---
name: generating-onboarding-dashboard
description: Generate a visual HTML onboarding-progress dashboard for all new hires. Reads 5 preparation nodes from HCM GET /api/candidates and workflow.json for the gate badge. Does not render probation-review cells (those live in local review-state; HCM review API will be retired). Optionally publish to OpenClaw Canvas. Does not write to HCM.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# generating-onboarding-dashboard

把所有新员工的入职进度，汇成一张可视化 HTML 看板，并发布到 OpenClaw Canvas 供浏览器查看。

## 何时用这个 Skill

HR 同时带多个新人，每个人的入职都散落在不同系统里——光看文件看不出全局。这个 Skill 在两种情况用：

- **要一张入职进度总览** —— 有人问「现在这批新人入职都到哪一步了」「谁卡住了」时，生成一张看板一眼看清。
- **状态有更新后刷新看板** —— HCM 中某部门更新了节点状态后，重跑这个 Skill 即可拿到最新快照。

## 数据来源

- **花名册与五部门准备节点**：HCM `GET /api/candidates`（只读）
- **审批门角标**：本机 `stub-state/<pinyin>/workflow.json`（HCM 无此字段）
- **不展示试用期 review**（本地 `review-state/` 维护，不进本看板；HCM review API 后续作废）
- **不向 HCM 写入**

HCM 不可达时脚本会报错退出（exit 5），不会用本地数据冒充。

## 工作流程

### 第 1 步 · 生成看板

```bash
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh
```

不传参数时，看板写到 `<workspace>/onboarding-dashboard.html`；要指定输出路径就在命令后加一个路径参数。

脚本做三件事：

1. **从 HCM 获取候选人** —— 调用 `GET /api/candidates` 获取花名册与五部门准备节点。
2. **读审批门角标** —— 对每个候选人，读本机 `stub-state/<pinyin>/workflow.json` 获取审批流程状态（HCM 不存此字段）。
3. **生成 HTML 看板 + 打印进度摘要** —— 每名新员工一张卡片（5 准备节点 + 角标）；终端打印「[角标] 准备 X/5 · 整体 Z%」。

### 第 2 步 · 发布到 Canvas（默认推荐）

```bash
# 一键：生成 + 发布（覆盖已有文档）
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force

# 或分步
python3 skills/generating-onboarding-dashboard/scripts/publish_to_canvas.py \
  onboarding-dashboard.html onboarding-dashboard --force
```

**强约束**：

- canvas-id 必须纯 ASCII，约定固定为 **`onboarding-dashboard`**。
- 同名已存在时必须显式 `--force`，否则 exit 5。
- 浏览器推荐打开 **18999** 反代 URL。

推荐 URL：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html
```

## 关键规则

- 看板数据来自 HCM 五节点 + 本机审批门角标，绝不编造。HCM API 不可达时脚本直接退出，不用本地文件冒充。
- **不渲染试用期 review。** 跟进在本地 `review-state/`，不进本看板。本 Skill **只读**，不调用 `sync-reviews-if-ready`、不注册 Cron。
- **「待审批」≠「已通过」。** 是否卡在审批门，以卡片角标的 `workflow.json` 为准。
- **看板不缓存旧值。** HCM 数据变了，重跑这个 Skill 就刷新；刷新后记得 `--publish --force` 覆盖 Canvas。
- **Canvas id 禁止中文。** 只用 `onboarding-dashboard`。
- 5 个准备节点的含义、状态归类，见 → `references/dashboard-spec.md`。
