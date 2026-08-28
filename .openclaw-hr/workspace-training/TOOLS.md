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

Add whatever helps you do your job. This is your cheat sheet.

## 培训业务 Skill 清单

培训业务专属 Skill 装在 `skills/` 目录下。这一节说明「做什么 / 什么时候用 / 调用要点」。

### generating-training-materials

- **做什么**：把 `source-docs/` 里的培训素材，经 ADDIE 五阶段流水线，生成一套内在自洽的培训物料——8 份 Markdown；**交付前按评测场景自我校验**。
- **什么时候用**：业务部门要办一场内训、需要一整套培训物料时。注意"一整套"不是一份 PPT——只要 PPT 是没把握住需求的。
- **形态**：`scripts/training-run.sh generate` 驱动 7 次 LLM HTTP + 落盘 + `self_check.py`。Agent 不要自己 write 八份长文。
- **调用要点**：
  - `bash scripts/training-run.sh generate --theme 信息安全意识`（全量加 `--force`）
  - 结束句认 stdout 的 `RESULT:`；未通过不得声称已交付。
  - 讲师手册禁止逐字稿。

## Related

- [Agent workspace](/concepts/agent-workspace)
