# generating-onboarding-dashboard 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把每个新员工入职流程的 5 个准备节点 + 审批门角标 + 本地试用期跟进汇成一张可视化 HTML 看板。准备节点读 HCM `GET /api/candidates`；角标读本机 `workflow.json`；7/30/60/90 读 `review-state/reviews.json`。

## 评测场景

### 场景 1 · 生成入职进度看板

- 输入：HCM 花名册有若干在职新员工；本机可有 `stub-state/<pinyin>/workflow.json`
- query：生成一份新员工入职进度看板
- expected_behavior：
  - 产出一个 HTML 文件，每个在职新员工一张卡片
  - 每张卡片含 5 个准备节点状态 + 审批门角标 + 「试用期跟进」区块（已开通才画出 7/30/60/90 四格；未开通只留一行说明，不画空节点）
  - 准备节点状态来自 HCM，跟进来自本地表，看板不编造任何状态
  - 终端打印每个员工的「准备 X/5 · 整体 Z%」摘要

### 场景 2 · 看板数据随真实状态刷新

- 输入：跑过一次看板后，HCM 中某员工某准备节点从 pending 变为 completed
- query：重新生成看板
- expected_behavior：
  - 该员工准备完成数 +1，整体进度百分比相应变化
  - 看板是真实状态的快照——HCM 变了重跑即刷新，不缓存旧值
  - 本地 `review-state/` 增减记录**会**改变试用期跟进格子，不改变 5 节点进度百分比

### 场景 3 · 看板覆盖多名员工

- 输入：HCM 花名册有多名员工（如 员工1 / 员工2）
- query：生成看板
- expected_behavior：
  - 看板列出全部花名册员工，不漏不重
  - 顶部汇总「在职新员工 N 人 · 平均进度 M%」与各卡片数据一致

### 场景 4（边界）· 某员工节点缺失

- 输入：HCM 中某员工缺了部分准备节点
- query：生成看板
- expected_behavior：
  - 缺失的节点显示「未就绪」，不报错崩溃
  - 看板仍能完整生成，缺失节点如实标注而非编造已完成

### 场景 5 · 发布到 Canvas

- 输入：场景 1 已生成 `onboarding-dashboard.html`
- query：把入职进度看板发到 Canvas / 浏览器能看
- expected_behavior：
  - 调用 `publish_to_canvas.py`（或 `build-dashboard.sh --publish --force`）
  - canvas-id 为 ASCII `onboarding-dashboard`（拒绝中文 id）
  - 落盘 `$OPENCLAW_STATE_DIR/canvas/documents/onboarding-dashboard/index.html`（本仓 profile：`/opt/openclaw-hr/.openclaw-hr/canvas/...`，不要把 `~/.openclaw-hr` 当现行路径）
  - stdout 打印 18999 推荐 URL；浏览器可打开该页
  - 同名已存在且未 `--force` 时 exit 5，不静默覆盖
  - 打开后的页面有「试用期跟进」标题

## 基线测试（没有 Skill 时）

见本实验记录 CP3 · 步骤 2。
