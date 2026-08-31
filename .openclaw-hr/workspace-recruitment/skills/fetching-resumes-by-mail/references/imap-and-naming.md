# IMAP 收取与命名细则

## 1. 搜索条件

`fetch_resumes.py` live 后端固定：

```
UNSEEN + (可选) SINCE <date>
```

- 默认：未读 + `--days-ago 2`
- `--since YYYY-MM-DD` 显式覆盖日期下限
- **注意**：部分邮箱（如 QQ IMAP）对 `SINCE` 支持不稳定；以 `UNSEEN` 为准。客户端可再按 `MailSummary.date` 过滤今天。

`fetch_resumes.py` **不会**自动打 `\Seen`。标已读交给 `mark_read.py`。

## 2. 姓名 / 岗位识别

| 输入 | 是否使用 |
|---|---|
| 简历 PDF/DOCX 正文 | ✅ 唯一来源 |
| 邮件主题 | ❌ |
| 邮件正文 | ❌ |
| 附件文件名 | ❌ |

流程：抽文本（截断约 2000 字）→ 对话模型（默认 `mimo-v2.5-pro`）→ JSON `{name, position}`。  
缓存 key = 文件内容 sha256；失败结果不缓存。

`--no-llm` 仅离线兜底，生产不要开。

## 3. 落盘命名、身份与 HR 待办

- 有标题：`{name}-{position}{ext}`。无标题：`{name}-待确认{ext}` + `needs-hr`（`position-uncertain`）。**不阻塞解析评分**。
- **同一人**覆盖后登记 `needs-pipeline.jsonl`；收信进程不作废后的解析/评分，由同一轮 Skill 重跑。
- 同名说不清：另存一份 + `identity-ambiguous`，流程走完，HR 再合并。
- 字节相同：`content-already-saved`。

## 4. 附件处理

白名单：`.pdf` `.docx` `.zip` `.rar`（magic number 二次校验）。

QQ 网页端/客户端常把简历标成 **`Content-Disposition: inline`**，有时只有 `Content-Type` 的 `name=`、甚至没有文件名。脚本 **walk 整封 MIME**，不依赖 `attachment` 或 imap-tools 的 `m.attachments`（后者会漏掉「无 filename 且无 Content-ID」的 part）。按后缀 / Content-Type / 文件头识别；内嵌图片、正文 html 仍丢弃。

**QQ 超大附件（文件中转站）**：主题像 `张娜_….pdf`，HTML 里是 `QQMailBigAttach` + `wx.mail.qq.com/ftn/download`，**MIME 里没有 PDF**。IMAP 授权码下不了中转站文件（链接打开是网页登录页）。脚本会记 `skipped_files.reason = qq-ftn-not-in-mime`。请发信方改用「普通附件」，不要用超大附件。

- 直接附件或内嵌 pdf/docx → 识别后落盘
- zip/rar → 安全解压后只提内层 pdf/docx（防 zip-slip / zip-bomb）
- 其它后缀一律丢弃

## 5. 环境变量

| 变量 | 用途 |
|---|---|
| `IMAP_USER` / `IMAP_PASS` | 登录 |
| `IMAP_HOST` / `IMAP_PORT` | 默认 qq 993 |
| `MAIL_FOLDER` | 默认 INBOX |
| `XIAOMI_API_KEY` / `LLM_API_KEY` | 收信改名用对话模型 |
| `FETCH_LLM_MODEL` / `FETCH_LLM_BASE_URL` | 可选覆盖（默认 mimo-v2.5-pro） |

推荐：`source ~/.openclaw-hr/env.sh`。

## 6. Mock 自测

```bash
# 在 playground 目录有 inbox-test 样本时：
python3 skills/fetching-resumes-by-mail/scripts/seed_mock_mailbox.py --clean --max-emails 3
python3 skills/fetching-resumes-by-mail/scripts/fetch_resumes.py --backend mock --inbox-dir inbox --no-llm
```

生产路径用 `--backend live`，不要把授权码写进命令行历史。
