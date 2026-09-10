# Canvas 发布约束 · 入职进度看板

> 把 `onboarding-dashboard.html` 发布到 OpenClaw Canvas host，约束与招聘侧画像发布同源。
> 招聘侧完整事故复盘见 `workspace-recruitment/.../references/canvas-publishing.md`；本文件只写看板差异与必守约束。

## 0. 流程两步（看板）

```
[1] render  · build-dashboard.py / .sh     → <workspace>/onboarding-dashboard.html
[2] publish · publish_to_canvas.py         → $OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html
```

看板由本 Skill 自己生成，无需独立 Node 校验闸；`publish_to_canvas.py` 仍做 HTML/id/落盘 fail-fast。

一键：

```bash
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh --publish --force
```

分步：

```bash
bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh
python3 skills/generating-onboarding-dashboard/scripts/publish_to_canvas.py \
  onboarding-dashboard.html onboarding-dashboard --force
```

## 1. 约定 canvas-id

| 用途 | ASCII id |
|---|---|
| 入职进度总览看板 | `onboarding-dashboard` |

看板是**全员总览页**，不是按人一份——固定一个 id 即可。重生成后用 `--force` 覆盖。

**禁止**用中文 id（如 `入职看板`）——Canvas 路由只收 `[A-Za-z0-9._-]+`。

## 2. 必守约束（与招聘侧相同）

1. **id** 匹配 `/^[A-Za-z0-9._-]+$/`，长度 ≤ 80，不以 `.` 开头，不含 `..`
2. 落盘文件名必须是 **`index.html`**（脚本强制）
3. 路径：`$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html`（本仓 `/opt/openclaw-hr/.openclaw-hr/canvas/...`）。未设 `OPENCLAW_STATE_DIR` 时脚本才回退家目录，不要把 `~/.openclaw-hr` 当现行路径；勿误发到 `~/.openclaw/canvas`
4. HTML：UTF-8 无 BOM + `<!DOCTYPE html>` + `</html>`
5. 落盘：tempfile + `os.replace` 原子写入；默认不覆盖，需 `--force`
6. 浏览器看图用 **18999** 反代（无需 Bearer）；直连 18790 会被拦

推荐 URL：

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/onboarding-dashboard/index.html
```

## 3. Chat embed（可选）

```
[embed ref="onboarding-dashboard" type="canvas/document"]
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
