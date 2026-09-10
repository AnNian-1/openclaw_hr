# TOOLS.md · 总控 Router 本机笔记

Router **没有业务 Skill**。调度只用 OpenClaw 会话工具。

## 分发

- 新请求：`sessions_spawn`，`agentId` 为 `recruitment` / `onboarding` / `training` / `performance` / `er-admin`。
- spawn 后 `sessions_yield`。不要先 `sessions_send`，不要 `sessions_list` / `sessions_history` 空转。
- 并发：`agents.defaults.subagents.maxChildrenPerAgent` = **8**（只认 defaults，不能写在单个 Agent 的 `subagents` 里）。满了就告诉用户等，不要连打。
- 子 Agent 超时：`runTimeoutSeconds` = **1800**。超时/失败原样转述，不编造成功。

## 行政 task 后缀

出月报 / 员工1工资 / 查花名册薪资 / 政策问答 → spawn `er-admin`。

WebChat / CLI（无飞书 `ou_`）时，`task` 末尾加：

`通道=webchat，无飞书 ou_，按演示 HR 数据权限处理。`

## 培训 task 后缀

用户只要部分物料时，附加：`只生成用户点名的材料，不要扩展成全套 8 份培训包。`

## 乐奇眼镜

- image：`image` 读本地绝对路径，禁止 `web_fetch` / OSS。不 spawn。
- audio / video：只确认已收到，不转写、不 spawn。

## 不做

- 不在 `exec` 里跑业务脚本。
- 政策/评分/薪资/月报数字只来自子 Agent 回流。
- 不改 `openclaw.yaml` 的 bindings / toolsBySender。
