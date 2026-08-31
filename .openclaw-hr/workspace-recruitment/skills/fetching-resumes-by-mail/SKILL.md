---
name: fetching-resumes-by-mail
description: >-
  Fetch resume attachments from an enterprise mailbox over IMAP, rename them by
  candidate name and position extracted from the resume file itself via LLM, and
  optionally mark processed mails as seen. Use when the user asks to pull resumes
  from email/QQ mail/IMAP inbox, auto-collect job applications, or land
  attachments into inbox/ before parsing-resumes.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["IMAP_USER", "IMAP_PASS", "XIAOMI_API_KEY"]
---

# fetching-resumes-by-mail

从企业邮箱（IMAP）自动收取简历附件，落盘到 `inbox/`，交给下游 `parsing-resumes`。

## 何时用这个 Skill

- 要从 QQ / 企业邮箱拉投递简历
- 要把未读邮件里的 PDF/DOCX 简历落到 `inbox/`
- 收完后需要把已处理邮件标为已读（`\Seen`）

下游解析 / 画像 / 评分是别的 Skill 的事；本 Skill 只管「收信 → 落盘 →（可选）标已读」。

## 前置条件

Gateway / `recruitment-run.sh` 已注入 `IMAP_*` 与对话模型 Key。**不要**在 exec 里再写 `source … &&` 或 `--since $(date +%F)`：闸会直接 `allowlist miss`。Python 依赖应已装好，不要在 exec 里 `pip install`。

必需环境变量：`IMAP_USER`、`IMAP_PASS`；抽取姓名/岗位走当前对话模型环境，不要 DeepSeek。  
可选：`IMAP_HOST`（默认 `imap.qq.com`）、`IMAP_PORT`（默认 `993`）、`MAIL_FOLDER`（默认 `INBOX`）。

## 工作流程

按顺序做两步（第 2 步可选，但生产建议做）。

### 第 1 步 · 收取并落盘

```bash
bash scripts/fetch-mail.sh
```

常用参数：

| 参数 | 默认 | 含义 |
|---|---|---|
| `--backend` | `mock` | `live` = 真 IMAP；`mock` = 本地 maildir |
| `--since YYYY-MM-DD` | — | 显式日期下限（优先于 `--days-ago`） |
| `--days-ago N` | `2` | 未读 + 今天往前 N 天 |
| `--no-llm` | off | 关掉 LLM，改用启发式（不推荐） |
| `--dry-run` | off | 只列候选，不写盘 |

成功标志：

- 打印 `[fetch] 落盘 N 份简历 ...`
- `inbox/` 出现 `姓名-岗位.pdf|docx` 或 `姓名-待确认.pdf|docx`
- `inbox/.fetched-mail.jsonl` 追加本轮元数据
- 有不确定项时 `inbox/needs-hr.jsonl` 有新 pending

### 第 2 步 · 标已读

只对「本轮有落盘（含覆盖、含待确认）」的 UID 打 `\Seen`。

```bash
# 从 jsonl 抽出本轮相关 UID 后：
bash scripts/recruitment-run.sh python3 skills/fetching-resumes-by-mail/scripts/mark_read.py --uid "3716 3717 3718"
```

`mark_read.py` 也支持 `--subject "简历" --days-ago 2` 模糊匹配；生产优先用精确 UID。

## 硬规则（必须照做）

1. **只拉未读**：IMAP 条件固定 `seen=False`；已读不会再拉。
2. **姓名/岗位只读简历文件正文**（PDF→pdfminer / DOCX→python-docx → LLM）。**不看**邮件主题、正文、附件文件名。
3. **落盘命名**：有求职意向标题则为 `姓名-岗位.ext`；否则 `姓名-待确认.ext`，并写入 `needs-hr.jsonl`。**解析评分照常跑**，HR 事后可改岗位。
4. **同一人覆盖**：姓名+电话（或邮箱）相同 → 覆盖旧 PDF，作废该 stem 的 parsed/clean/score，并写入 `needs-pipeline.jsonl`。收信**不会**自己重跑 LLM。同一轮必须对该 stem：转 MD → 解析 → 脱敏 → `batch_rank` 增量，再 `hr_queue.py pipeline-done <stem>`。同名异号当两个人。同名说不清 → **仍落盘**成另一份 + `needs-hr`，流程走完，HR 再合并或保留。
5. **Agent 合同**：`needs-hr` 只通知、不拦流水线；`needs-pipeline` 必须在本轮重跑下游。`hr_queue.py list` / `list-pipeline`
6. **附件白名单**：只保留 pdf/docx；zip/rar 解压后再提 pdf/docx；png/jpg/… 丢弃。QQ **内嵌（inline）** 简历也收，不要求 `Content-Disposition: attachment`。**QQ「超大附件」收不到**：那是文件中转站链接，IMAP 里没有文件；让对方用普通附件重发。
7. **不删不挪原邮件**：只允许打 `\Seen`；文件夹移动由 HR 自己做。
8. **密钥不进 git**：IMAP 授权码 / API Key 只走 `env.sh` / 环境变量。

## 产物

| 路径 | 内容 |
|---|---|
| `inbox/姓名-岗位.ext` 或 `姓名-待确认.ext` | 简历附件 |
| `inbox/<文件>.meta.json` | 意向是否锁定、是否抽出电话/邮箱（不含号码明文） |
| `inbox/.identity.json` | 姓名 + 电话/邮箱哈希，用于同一人判定 |
| `inbox/needs-hr.jsonl` | 待 HR 决策（岗位模糊、身份不确定） |
| `inbox/.fetched-mail.jsonl` | 每封一行：uid / subject / saved_files / skipped_files |

## 下游衔接

落盘后照常 office-to-md → parsing → 评分。`needs-hr` 边跑边问 HR。若有 `needs-pipeline`，同一轮必须先把那些 stem 重解析并增量评分。

## 参考

- IMAP / 命名 / 身份覆盖 / needs-hr → [references/imap-and-naming.md](references/imap-and-naming.md)
- Playground 原型目录（开发用）：`hr_claw_hub/playground/2.step_B_recruitment/playground/2.step_get_resume_by_mail/`
