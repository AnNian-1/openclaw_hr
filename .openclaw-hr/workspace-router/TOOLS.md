# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Router 调度（本机）

- spawn：`sessions_spawn`，`agentId` 为 `recruitment` / `onboarding` / `training` / `performance` / `er-admin`。
- 并发：`agents.defaults.subagents.maxChildrenPerAgent` = **8**（本机 OpenClaw 2026.5.12 只认 defaults，不能写在单个 Agent 的 `subagents` 里）。满了就告诉用户等，不要连打。
- 子 Agent 超时：`runTimeoutSeconds` = **1800**。超时把原因转述，不编造成功。
- 培训 `task`：用户只要手册+试题时，附加「不要扩展成全套 8 份」。
- 不在 exec 里跑业务脚本。政策/评分数字只来自子 Agent 回流。

## Related

- [Agent workspace](/concepts/agent-workspace)
