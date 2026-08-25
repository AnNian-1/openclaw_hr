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
      env: ["IMAP_USER", "IMAP_PASS", "DEEPSEEK_API_KEY"]
---

# fetching-resumes-by-mail

从企业邮箱（IMAP）自动收取简历附件，落盘到 `inbox/`，交给下游 `parsing-resumes`。

## 何时用这个 Skill

- 要从 QQ / 企业邮箱拉投递简历
- 要把未读邮件里的 PDF/DOCX 简历落到 `inbox/`
- 收完后需要把已处理邮件标为已读（`\Seen`）

下游解析 / 画像 / 评分是别的 Skill 的事；本 Skill 只管「收信 → 落盘 →（可选）标已读」。

## 前置条件

```bash
source ~/.openclaw-hr/env.sh   # 提供 IMAP_* 与 DEEPSEEK_API_KEY
pip install imap-tools pdfminer.six python-docx   # 若未装
```

必需环境变量：`IMAP_USER`、`IMAP_PASS`、`DEEPSEEK_API_KEY`。  
可选：`IMAP_HOST`（默认 `imap.qq.com`）、`IMAP_PORT`（默认 `993`）、`MAIL_FOLDER`（默认 `INBOX`）。

## 工作流程

按顺序做两步（第 2 步可选，但生产建议做）。

### 第 1 步 · 收取并落盘

```bash
python3 skills/fetching-resumes-by-mail/scripts/fetch_resumes.py \
  --backend live \
  --inbox-dir inbox \
  --since $(date +%F) \
  --llm-timeout 20
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
- `inbox/` 出现 `姓名-岗位.pdf|docx`
- `inbox/.fetched-mail.jsonl` 追加本轮元数据

### 第 2 步 · 标已读

只对「本轮有落盘，或因同姓名跳过」的 UID 打 `\Seen`：

```bash
# 从 jsonl 抽出本轮相关 UID 后：
python3 skills/fetching-resumes-by-mail/scripts/mark_read.py --uid "3716 3717 3718"
```

`mark_read.py` 也支持 `--subject "简历" --days-ago 2` 模糊匹配；生产优先用精确 UID。

## 硬规则（必须照做）

1. **只拉未读**：IMAP 条件固定 `seen=False`；已读不会再拉。
2. **姓名/岗位只读简历文件正文**（PDF→pdfminer / DOCX→python-docx → LLM）。**不看**邮件主题、正文、附件文件名。
3. **落盘命名**：`姓名-岗位.ext`。
4. **同姓名不落盘**：`inbox/` 已有同「姓名」文件时跳过，记 `name-already-exists`，**不覆盖**。
5. **附件白名单**：只保留 pdf/docx；zip/rar 解压后再提 pdf/docx；png/jpg/… 丢弃。
6. **不删不挪原邮件**：只允许打 `\Seen`；文件夹移动由 HR 自己做。
7. **密钥不进 git**：IMAP 授权码 / API Key 只走 `env.sh` / 环境变量。

## 产物

| 路径 | 内容 |
|---|---|
| `inbox/姓名-岗位.ext` | 简历附件 |
| `inbox/.fetched-mail.jsonl` | 每封一行：uid / subject / saved_files / skipped_files |

## 下游衔接

落盘后交给：

1. `office-to-md-v2`（若还需转 Markdown）
2. `parsing-resumes` → `auditing-extraction` → 评分 / 画像

## 参考

- IMAP / 命名 / 同姓名跳过细则 → [references/imap-and-naming.md](references/imap-and-naming.md)
- Playground 原型目录（开发用）：`hr_claw_hub/playground/2.step_B_recruitment/playground/2.step_get_resume_by_mail/`
