# generating-onboarding-dashboard 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把每个新员工入职流程的 9 个节点状态（5 准备节点 + 4 review 节点）汇成一张可视化 HTML 看板，数据全部读自真实落盘文件。

## 评测场景

### 场景 1 · 生成入职进度看板

- 输入：workspace 根已有若干员工的 `stub-state*` 与 `review-state/` 落盘文件
- query：生成一份新员工入职进度看板
- expected_behavior：
  - 产出一个 HTML 文件，每个在职新员工一张卡片
  - 每张卡片含 5 个准备节点 + 4 个 review 节点的状态
  - 每个节点状态来自真实落盘的 JSON 文件，看板不编造任何状态
  - 终端打印每个员工的「准备 X/5 · review Y/4 · 整体 Z%」摘要

### 场景 2 · 看板数据随真实状态刷新

- 输入：跑过一次看板后，某员工新增了一条 review 落盘记录
- query：重新生成看板
- expected_behavior：
  - 该员工的 review 节点数 +1，整体进度百分比相应变化
  - 看板是真实状态的快照——状态文件变了重跑即刷新，不缓存旧值

### 场景 3 · 看板覆盖多名员工

- 输入：workspace 根有 3 名员工的状态目录（如 张磊 / 陈静 / 周敏）
- query：生成看板
- expected_behavior：
  - 看板列出全部 3 名员工，不漏不重
  - 顶部汇总「在职新员工 N 人 · 平均进度 M%」与各卡片数据一致

### 场景 4（边界）· 某员工状态文件缺失

- 输入：某员工的 `stub-state` 目录里缺了部分节点 JSON（如还没跑完入职工作流）
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
  - 落盘 `$OPENCLAW_STATE_DIR/canvas/documents/onboarding-dashboard/index.html`（或 `~/.openclaw-hr/canvas/...`）
  - stdout 打印 18999 推荐 URL；浏览器可打开该页
  - 同名已存在且未 `--force` 时 exit 5，不静默覆盖

## 基线测试（没有 Skill 时）

见本实验记录 CP3 · 步骤 2。
