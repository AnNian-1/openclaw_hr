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
- **形态**：markdown 指令型 Skill + 交付前结构自检脚本。能力 = `SKILL.md` 步骤 0→8 + `references/stage-prompts.md`（7 段模板）+ `scripts/self_check.py` + `evals/eval-cases.md`（验收说明书）。
- **评测 / 自检（必做）**：
  - 说明书：`skills/generating-training-materials/evals/eval-cases.md`（作者评测 + Agent 交付前自检，两用）。
  - 结构自检：`python3 skills/generating-training-materials/scripts/self_check.py --outdir <物料目录>`
  - 自检未通过不得声称「全套物料已交付」。细则见 SKILL.md 步骤 8。
- **调用要点**：
  - 严格按 SKILL.md 的步骤 0→8 顺序走，不跳步；步骤 8 不可省。
  - 每一步产出落盘到 `training-materials/`（或主题子目录）后，再进下一步。
  - 后一步开工前先读前一步指定的产出文件——这是流水线阶段承接的硬约束。
  - 讲师手册（步骤 3）只要讲解要点 + 互动 + 控场提示，**不要写逐字稿**。
  - 物料生成读写文件（`group:fs`）；自检需 `python3`。

## Related

- [Agent workspace](/concepts/agent-workspace)
