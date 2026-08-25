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

流程：抽文本（截断约 2000 字）→ DeepSeek（默认 `deepseek-v4-flash`）→ JSON `{name, position}`。  
缓存 key = 文件内容 sha256；失败结果不缓存。

`--no-llm` 仅离线兜底，生产不要开。

## 3. 落盘命名与去重

- 文件名：`{name}-{position}{ext}`，经 `_safe_save_name` 清洗。
- **同姓名跳过**：扫描 `inbox/` 非隐藏文件；按 `-` 切段后任一段等于识别姓名即视为已存在
  （兼容新格式 `张磊-后端技术专家.pdf` 与旧格式 `resume-tech-01-张磊-后端开发.pdf`）。
  命中则不写盘，`skipped_files.reason = name-already-exists (...)`。
- 不同姓名、同岗位：正常各自落盘。

## 4. 附件处理

白名单：`.pdf` `.docx` `.zip` `.rar`（magic number 二次校验）。

- 直接附件 pdf/docx → 识别后落盘
- zip/rar → 安全解压后只提内层 pdf/docx（防 zip-slip / zip-bomb）
- 其它后缀一律丢弃

## 5. 环境变量

| 变量 | 用途 |
|---|---|
| `IMAP_USER` / `IMAP_PASS` | 登录 |
| `IMAP_HOST` / `IMAP_PORT` | 默认 qq 993 |
| `MAIL_FOLDER` | 默认 INBOX |
| `DEEPSEEK_API_KEY` | LLM 识别 |
| `FETCH_LLM_MODEL` / `FETCH_LLM_BASE_URL` | 可选覆盖 |

推荐：`source ~/.openclaw-hr/env.sh`。

## 6. Mock 自测

```bash
# 在 playground 目录有 inbox-test 样本时：
python3 skills/fetching-resumes-by-mail/scripts/seed_mock_mailbox.py --clean --max-emails 3
python3 skills/fetching-resumes-by-mail/scripts/fetch_resumes.py --backend mock --inbox-dir inbox --no-llm
```

生产路径用 `--backend live`，不要把授权码写进命令行历史。
