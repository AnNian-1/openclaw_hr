# 记忆 / 脱敏 — 待办（按日跟进）

## 2026-09-03 — recruitment ASR 未脱敏进做梦报告

**现象**：22:00 第一轮 dreaming 后，`workspace-recruitment/memory/dreaming/light/2026-09-03.md` 命中闸词 `张磊` / `zhanglei`（ASR 面试音频转写与会话 corpus 原样摘要）。

**当晚处理**：
- 已手工脱敏：`张磊` → `员工2`，`interview-zhanglei-tech2` → `interview-yuangong2-tech2`
- `dream-report-gate.sh --check` 与本域 18 份报告全扫：**退出 0**
- **未**改 `MEMORY.md`，**未** `promote --apply`

**仍留 soft（闸扫不到，合并 MEMORY.md 前再改）**：
| 位置 | 原文 | 建议 |
|------|------|------|
| light/2026-09-03.md ~43 行 | `` `江政宾-待确认.pdf` `` | `` `面试者2-待确认.pdf` `` 或夹具名 |
| light/2026-09-03.md ~68 行 | `云南大学` | `某某大学1` |

**根因（改天做）**：在 **fetch-mail 落盘文件名 / 简历解析 / ASR 纪要产出** 环节脱敏，避免每晚 dreaming 从 session corpus 再带出真名。参见 `docs/脱敏规则.md`。

**复跑记录**：`ops/replay-verify-20260903.md` §「勿自动 promote」已含 `云南大学` / `zhanglei`·张磊。

**下次跟进**：改 soft 残留 **或** 补 ASR/收邮件脱敏脚本；合并 recruitment `MEMORY.md` 前再跑 gate + 人审。
