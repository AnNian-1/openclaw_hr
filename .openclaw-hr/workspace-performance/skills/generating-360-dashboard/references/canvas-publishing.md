# Canvas 发布约束 · 360 反馈看板

> 把 `source_feedback/<slug>/report.html` 发布到 OpenClaw Canvas host。
> 约束与入职看板 / 招聘侧画像发布同源；本文件只写 360 看板差异与必守约束。

## 0. 流程两步

```
[1] render  · build_dashboard.py / .sh
            → 评分读 aggregated-data.json；语义必读 aggregated-report.md
            → feedback-360/source_feedback/<slug>/report.html
[2] publish · publish_to_canvas.py
            → $OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html
```

一键（推荐）：

```bash
bash skills/generating-360-dashboard/scripts/build_dashboard.sh \
  feedback-360/source_feedback/<slug> --publish --force
```

分步：

```bash
python3 skills/generating-360-dashboard/scripts/build_dashboard.py \
  feedback-360/source_feedback/<slug>
python3 skills/generating-360-dashboard/scripts/publish_to_canvas.py \
  feedback-360/source_feedback/<slug>/report.html \
  feedback-360-<slug> --force
```

## 1. 约定 canvas-id

| 用途 | ASCII id |
|---|---|
| 某人 360 看板 | `feedback-360-<slug>`（例 `feedback-360-yuangong1`） |

按人一份；`<slug>` 取人员目录名（拼音，已是 ASCII）。**禁止**中文 id。

## 2. 必守约束

1. **id** 匹配 `/^[A-Za-z0-9._-]+$/`，长度 ≤ 80，不以 `.` 开头，不含 `..`
2. 落盘文件名必须是 **`index.html`**（脚本强制）
3. 路径：`$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html`；未设时优先 `~/.openclaw-hr/canvas/...`（HR profile），勿误发到 `~/.openclaw/canvas`
4. HTML：UTF-8 无 BOM + `<!DOCTYPE html>` + `</html>`
5. 落盘：tempfile + `os.replace` 原子写入；默认不覆盖，需 `--force`
6. 浏览器看图用 **18999** 反代（无需 Bearer）；直连 18790 会被拦

推荐 URL（员工1示例）：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/feedback-360-yuangong1/index.html
```

## 3. Chat embed（可选）

```
[embed ref="feedback-360-yuangong1" type="canvas/document"]
```

WebChat 通常不渲染 embed，以 18999 URL 为主。

## 4. 退出码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 参数错 |
| 2 | 源 HTML 不存在 |
| 3 | id / HTML 校验失败 |
| 4 | 落盘 IO 失败 |
| 5 | 目标已存在且未 `--force` |
