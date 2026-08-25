# Canvas 发布约束 · HR 月报

> 把 `hr-monthly-report-<YYYY-MM>.html` 发布到 OpenClaw Canvas host，约束与入职看板 / 招聘侧画像发布同源。
> 入职侧参考：`workspace-onboarding/.../references/canvas-publishing.md`。

## 0. 流程两步（月报）

```
[1] render  · generate_monthly_report.py   → report-output/hr-monthly-report-<YYYY-MM>.html
[2] publish · publish_to_canvas.py         → $OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html
```

月报由本 Skill 自己生成；`publish_to_canvas.py` 做 HTML/id/落盘 fail-fast。

一键（Cron / 推荐）：

```bash
bash skills/generating-monthly-report/scripts/run_monthly_report.sh --force
# 默认带 --publish --force
```

指定月份：

```bash
bash skills/generating-monthly-report/scripts/run_monthly_report.sh 2026-05
# 或
python3 skills/generating-monthly-report/scripts/generate_monthly_report.py 2026-05 --publish --force
```

只生成不发布：

```bash
bash skills/generating-monthly-report/scripts/run_monthly_report.sh --force --no-publish
```

## 1. 约定 canvas-id

| 用途 | ASCII id |
|---|---|
| HR 月报（当前最新一期） | `hr-monthly-report` |

workspace 里保留带月份的文件名；Canvas 上固定一个 id，每次重出用 `--force` 覆盖——浏览器始终打开同一 URL 看最新月报。

**禁止**用中文 id（如 `HR月报`）——Canvas 路由只收 `[A-Za-z0-9._-]+`。

## 2. 必守约束

1. **id** 匹配 `/^[A-Za-z0-9._-]+$/`，长度 ≤ 80，不以 `.` 开头，不含 `..`
2. 落盘文件名必须是 **`index.html`**（脚本强制）
3. 路径：`$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html`；未设时优先 `~/.openclaw-hr/canvas/...`（HR profile），勿误发到 `~/.openclaw/canvas`
4. HTML：UTF-8 无 BOM + `<!DOCTYPE html>` + `</html>`
5. 落盘：tempfile + `os.replace` 原子写入；默认不覆盖，需 `--force`
6. 浏览器看图用 **18999** 反代（无需 Bearer）；直连 18790 会被拦

推荐 URL：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/hr-monthly-report/index.html
```

## 3. Chat embed（可选）

```
[embed ref="hr-monthly-report" type="canvas/document"]
```

仅 paired native app 可靠渲染；WebChat 通常只显示原文——仍可发，但要以 18999 URL 为主。

## 4. 退出码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 参数错 |
| 2 | 源 HTML 不存在 |
| 3 | id / HTML 校验失败 |
| 4 | 落盘 IO 失败 |
| 5 | 目标已存在且未 `--force` |
