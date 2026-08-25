---
name: generating-onboarding-dashboard
description: Generate a visual HTML onboarding-progress dashboard for all new hires, then optionally publish it to OpenClaw Canvas host for browser viewing. Use this skill when someone asks for an onboarding progress overview, a status board, or wants to see where new hires stand. It auto-discovers every new hire from stub-state/<pinyin>/ (and legacy stub-state-*), reads workflow.json for the current gate, the 5 preparation nodes and 4 probation-review nodes from real on-disk JSON, writes a one-page HTML dashboard, and can copy it to canvas/documents/onboarding-dashboard/index.html (ASCII id required; view via nginx 18999). The dashboard never invents any status — every node reflects a real state file.
metadata:
  openclaw:
    requires:
      bins: ["bash", "python3"]
---

# generating-onboarding-dashboard

把所有新员工的入职进度，汇成一张可视化 HTML 看板，并发布到 OpenClaw Canvas 供浏览器查看。

## 何时用这个 Skill

HR 同时带多个新人，每个人的入职都散落在不同的状态文件里——光看文件看不出全局。这个 Skill 在两种情况用：

- **要一张入职进度总览** —— 有人问「现在这批新人入职都到哪一步了」「谁卡住了」时，生成一张看板一眼看清。
- **状态有更新后刷新看板** —— 某个新员工跑完了入职工作流的某一步、或某个 review 节点落了盘，重跑这个 Skill 即可拿到最新快照。

看板汇总每名新员工的 **9 个节点 + 流程角标**：入职审批工作流的 5 个准备节点（合同 / IT 账号 / 设备 / Buddy / 培训）+ 试用期跟进的 4 个 review 节点（第 7 / 30 / 60 / 90 天）；卡片右上角角标读自 `workflow.json`（如「等待审批 · 合同审批门」）。

## 工作流程

### 第 1 步 · 生成看板

```bash
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh
```

不传参数时，看板写到 `<workspace>/onboarding-dashboard.html`；要指定输出路径就在命令后加一个路径参数。

脚本做三件事：

1. **自动发现新员工** —— 扫描 workspace 根下所有 `stub-state*` 目录：
   - **新结构**：`stub-state/<pinyin>/`（每个拼音子目录一名员工）
   - **旧结构**：`stub-state-<姓名>/`（目录本身就是一名员工）
   空壳目录（既无 `contract.json` 也无 `workflow.json`）跳过；同名时优先保留新结构。姓名 / 岗位从 `contract.json` 或 `workflow.json` 读出。
2. **读真实状态** —— 5 个准备节点读自候选人目录下的 stub JSON；流程角标读自同目录 `workflow.json`；4 个 review 节点读自 `review-state/`。
3. **生成 HTML 看板 + 打印进度摘要** —— 每名新员工一张卡片（含角标与 9 节点进度）；终端打印「[角标] 准备 X/5 · review Y/4 · 整体 Z%」。

### 第 2 步 · 发布到 Canvas（默认推荐）

生成后把 HTML 复制到 OpenClaw Canvas host，HR 用浏览器打开即可（不必下载本地文件）：

```bash
# 一键：生成 + 发布（覆盖已有文档）
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force

# 或分步
python3 skills/generating-onboarding-dashboard/scripts/publish_to_canvas.py \
  onboarding-dashboard.html onboarding-dashboard --force
```

**强约束**：

- canvas-id 必须纯 ASCII，约定固定为 **`onboarding-dashboard`**（总览页，不是按人一份）。
- 落盘路径为 `$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html`（或 `~/.openclaw-hr/canvas/...`）。
- 同名已存在时必须显式 `--force`，否则 exit 5。
- 浏览器推荐打开 **18999** 反代 URL（无需 Bearer）；直连 18790 会被拦。

推荐 URL：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html
```

发布约束与事故复盘见 → `references/canvas-publishing.md`。

## 看板生成后做什么

脚本退出码 0 = 看板已生成（若带 `--publish` 则含发布成功）。终端摘要确认人数与进度；把 18999 URL 交给 HR，或在 Chat 发可选 embed：

```
[embed ref="onboarding-dashboard" type="canvas/document"]
```

（WebChat 通常不渲染 embed，以浏览器 URL 为主。）

## 关键规则

- **看板只反映真实状态文件，绝不编造。** 某个节点的 JSON 文件不存在时，看板把它显示成「未就绪」——这说明该新员工的入职工作流还没跑到产出这个节点的步骤。如实标注，不要替它填一个「已完成」。
- **「待审批」≠「已通过」。** 准备节点进审批门时是「待审批」（灰）；真人批准后才是「已审批 / 已通过」（绿）。是否卡在门上，以卡片角标的 `workflow.json` 为准，不要只看准备节点全绿就当流程走完。
- **新员工名单不手工维护。** 不要去脚本里写死员工名单——脚本靠扫描 `stub-state*` 自动发现。要让一名新员工出现在看板上，先用 `running-onboarding-workflow` 跑他的入职工作流。
- **看板不缓存旧值。** 状态文件变了，重跑这个 Skill 就刷新；刷新后记得 `--publish --force` 覆盖 Canvas。
- **Canvas id 禁止中文。** 只用 `onboarding-dashboard`；中文文件名可留在 workspace，发布 id 必须 ASCII。
- 9 个节点的含义、状态归类、目录约定，见 → `references/dashboard-spec.md`。
