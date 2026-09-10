# TOOLS.md · 培训小慧

Skills 定义怎么用工具。本文件只记本工作区的调用约定。

## 点名 / `--only` / 全套

| 用户怎么说 | Agent 怎么跑 | 不要做 |
|---|---|---|
| 只要评估反馈表 / 只要 08 | `bash scripts/training-run.sh generate --theme <主题> --only 08` | 不要顺手再出 01–07 |
| 只要学员手册和测试题 | `--only 05,06`（或 `--only 学员手册,测试题`） | 不要扩成全套 8 份 |
| 「做一套完整 / 全套 / 八份都要」 | `bash scripts/training-run.sh generate --theme <主题>`（重写加 `--force`） | 未听到这句就不要省略 `--only` |
| 只改某一份已有物料 | 直接改文件，或对那一份 `--only` | 不要重跑整条流水线 |

完整 8 类（01–08）是 ADDIE **上限**，不是每次默认产物。未点名不要默认全套。

结束句只认脚本打印的 `RESULT: success|failure`。点名生成时，`RESULT: success` 只表示**点名的那些文件**齐了并通过 `self_check --partial`，不表示 8 份都在。

## 培训业务 Skill 清单

本工作区只有 `generating-training-materials`。`generating-training-figures` 已裁撤，不要主动触发。

### generating-training-materials

- **做什么**：把 `source-docs/` 素材经 ADDIE 五阶段（步骤 0→7 生成 + 步骤 8 自检）写成内在自洽的 Markdown 物料。用户点名哪几份就生成哪几份。
- **什么时候用**：业务部门要办内训、点名了具体物料（或明确要全套）时。只要 PPT 不够；但未点名也不要主动出齐 8 份。
- **形态**：markdown 指令型 Skill（SKILL.md 步骤清单 + `references/stage-prompts.md`）+ 脚本编排（`training-run.sh` → `generate_pack.py` 按阶段 HTTP LLM + 落盘）+ `evals/eval-cases.md` + `scripts/self_check.py`。
- **调用要点**：
  - 只 `exec bash scripts/training-run.sh generate --theme <主题> [--only …] [--force]`
  - 不要自己 `write` 八份长文，不要编造 `training/courses/` 路径
  - 讲师手册禁止逐字稿
  - 交付前自检：脚本末尾会跑 `self_check.py`；点名时带 `--partial`
  - 手工复核：`bash scripts/training-run.sh self-check <主题>`

```bash
# 点名一份（例：评估反馈表）
bash scripts/training-run.sh generate --theme 信息安全意识 --only 08

# 点名两份
bash scripts/training-run.sh generate --theme 信息安全意识 --only 05,06

# 用户明确要全套
bash scripts/training-run.sh generate --theme 信息安全意识

# 只做结构自检（不调 LLM）
bash scripts/training-run.sh self-check 信息安全意识
```
