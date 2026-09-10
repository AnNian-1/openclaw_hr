# 查询 Skill 输出形态

stdout 是结构化 JSON，stderr 是人话摘要 +（halt 时）`---PROMPT---` 标记块。

单人查询成功时 JSON 关键字段：

| 字段 | 含义 |
|------|------|
| `source` | `hcm` / `hcm+workflow` / `hcm+pending` |
| `hcm_candidate` | HCM 花名册记录（含 `nodes[]`） |
| `workflow` | 本机 `workflow.json`；未 start 则为 null |
| `resume_token` | 在 `workflow.resume_token`（halt 时）；不要用 `approval_id` resume |
| `found_pending` | `contract` / `account` |
| `halts.<gate>.stub_changed_after_halt` | halt 后快照是否被改 |
| `halts.<gate>.current_prompt` | 与 lobster 同一份 `build-approval-prompt.py` |
| `halt_days` | 当前门已停留天数；≥3 只催办 |

`--all` 只输出花名册姓名列表（`forbid_invented_names: true`）。
