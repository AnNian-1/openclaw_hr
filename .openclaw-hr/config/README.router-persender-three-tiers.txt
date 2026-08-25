Router Per-Sender 三档权限配置流程备份 / 参考
========================================
文件:
  openclaw.router-persender-three-tiers.reference.yaml
    → 完整三档模板（用于讲解 / 对照配置流程）
  openclaw.20260726-as-is.reference.yaml
    → 2026-07-26 生产 openclaw.yaml 原文快照（员工档真实 ou + * deny）
  openclaw.yaml
    → 当前生效配置（仓库副本；运行时为 ~/.openclaw-hr/config/openclaw.yaml）

配置流程（飞书 1 Bot → router）:
  1) plugins.entries.feishu.enabled = true
  2) channels.feishu（websocket + appId/appSecret）
  3) bindings: feishu → agentId: router
  4) tools.toolsBySender 三档（只用 id:ou_xxx，不用 name:）:
       高: id:ou_REPLACE_HR_LEAD     allow ["*"]
       中: id:ou_REPLACE_BIZ_LEAD    可查/转派/exec，禁写文件
       低: id:ou_<真实员工>          IMA: sessions_spawn/yield/exec/read
       兜底: *                       deny ["*"]
  5) 普通员工政策问答走 er-admin + exec search_ima_policies.cjs
     （不要 deny group:runtime）
  6) 把 REPLACE_* 换成真实 open_id 后:
       config patch / 同步到 ~/.openclaw-hr/config/openclaw.yaml
       重启 Gateway（端口 18790）

说明:
  - reference 文件不是运行时生效文件；生效文件仍是 openclaw.yaml
  - WebChat/TUI 不注入 SenderName，未登记发送者命中 *
