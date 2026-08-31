# Canvas 发布约束 · 事故复盘手册

> 这份文档面向所有把候选人画像 / 报告 HTML 发布到 OpenClaw Canvas 插件托管目录的 agent。
> 写法是"事故复盘"式: 每一条约束背后都跟一个**具体的踩坑案例**。
> 当你在 skill / 脚本 / 文档里想打破"为什么必须 X"时, 翻这一节找答案。

## 目录

- 0. 流程三步
- 1. `<id>` 必须纯 ASCII `[A-Za-z0-9._-]+`
- 2. 文件名必须叫 `index.html`, 不能换
- 3. 落盘路径必须用 `$OPENCLAW_STATE_DIR/canvas/documents/`, 不用 workspace
- 4. HTML 必须 UTF-8 无 BOM + 含 DOCTYPE + 含 `</html>` 收尾
- 5. 同一候选人同一 ID 必须有去覆盖策略
- 6. `<id>` 长度 ≤ 80 + 不能以 `.` 开头 + 不能含 `..` + 不能是保留字
- 7. 落盘要 atomic (tempfile + rename)
- 8. `[embed ref="..."]` 在 WebChat 不渲染 · 但仍要发
- 9. 浏览器直接打开 18790 会被 Bearer 拦 · 用 18999 反代
- 10. ASCII 别名映射约定 (本 skill)

---

## 0. 流程三步

```
[1] render   · generate_profile.py            → 单文件 HTML 到 profile/output/
[2] validate · validate_profile_html.js       → 七区块 + 合规红线 + 与 ranking JSON 一致
[3] publish  · publish_to_canvas.py <html> <id>  → 把 HTML 落到 Canvas host
                                                ↑ 这一步踩坑最多
```

`publish_to_canvas.py` 是**最后一道闸门**——上面 1+2 跑通的 HTML, 经过这道闸再让 HR 看到。
所以这一步的 9 步校验链 (`[1/9]` ~ `[9/9]`) **一律 fail-fast, 不静默**。

---

## 1. `<id>` 必须纯 ASCII `[A-Za-z0-9._-]+`

### 事故复盘

2026-07-11: 用户意图发布候选人「员工1」画像, 习惯性传 `profile-员工1` 做 `<id>`。
Canvas 路由 `normalizeCanvasDocumentId()` 在 `install/node_modules/openclaw/dist/server-DXKfnO2y.js` 里:

```js
if (!/^[A-Za-z0-9._-]+$/.test(rawDocumentId)) {
  throw new Error("canvas document id invalid");
}
```

直接 `throw`—— HTTP 立刻 400, 浏览器拿不到文档。本地 mkdir `profile-员工1/` 目录是成功
了(文件系统支持 UTF-8), 但 Canvas **不会用这个路径 serve**。

### 解决

约定所有候选人 ID 一律 `profile-<pinyin-no-tones>`, 例如:

| 中文姓名 | ASCII 别名 |
|---|---|
| 员工1 | `profile-yuangong1` |
| 其他新人 | `profile-<pinyin-no-tones>` |

### 脚本报错形态

```
[3/9] id 'profile-员工1' 含非 ASCII / 全角 / emoji 字符: ['员', '工', '1'].
       Canvas 路由 normalizeCanvasDocumentId() 只接 [A-Za-z0-9._-].
       约定 ASCII 别名: 'profile-<pinyin-no-tones>', 如 'profile-yuangong1'.
exit=3
```

这一条**最重要**——错过它, 后面的 [4]~[9] 全白做。

---

## 2. 文件名必须叫 `index.html`, 不能换

### 事故复盘 (错把 HR 习惯带过来)

2026-07-11 排错时, HR 习惯把生成的 HTML 命名为 `员工1-简历.html` 直接传给 Canvas 路径。
Canvas 路由按**硬编码模板**拼路径:

```
$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html
```

(`/documents/<id>/index.html` 这段在 dist bundle 里是字面字符串。)

换名意味着即使 ID 通过校验, 文件落对了路径, Canvas 也**找不到文件**——返回 404。

### 解决

`publish_to_canvas.py` 强制把任何传入文件**复制到固定 `index.html`**。
不传 `<output_name>`, 你给的就是源路径, 落盘名字一律 `index.html`。

> 这条对你"看起来多余"是因为"如果加上 `?file=员工1.html` 的 query string 不行吗"
> —— Canvas 路由**不解析 query string**, 文件名必须是 `<id>/index.html` 的字面形态。

---

## 3. 落盘路径必须用 `$OPENCLAW_STATE_DIR/canvas/documents/`, 不用 workspace

### 事故复盘

agent 第一反应"我生成的文件在 workspace 里, 那就复制一份到 workspace/../canvas/"
——但 `workspace-recruitment/` 是 agent 的 workspace, 不是 Canvas host。

Canvas host 的物理根目录由 `config/openclaw.yaml` 里:

```yaml
plugins:
  entries:
    canvas:
      enabled: true
      config:
        host:
          enabled: true
          root: /root/.openclaw-hr/canvas        # ← 这里是根
          liveReload: false
```

这条 root 配置 + `documents` 子目录 + `<id>/index.html` 是 Canvas 的查找路径。
把 HTML 写到 `workspace-recruitment/canvas/profile-xxx/` 是**看不见的**。

### 解决

`publish_to_canvas.py` 启动时:

```
1. 读 $OPENCLAW_STATE_DIR  → /root/.openclaw-hr (本 profile 默认)
2. fallback $HOME/.openclaw/canvas
3. fallback $HOME/.openclaw-hr/canvas
4. /root/.openclaw-hr/canvas 永远兜底建好
```

不依赖 workspace, 不依赖当前工作目录, 不依赖 agent 进程状态。

---

## 4. HTML 必须 UTF-8 无 BOM + 含 DOCTYPE + 含 `</html>` 收尾

### 事故复盘 (4 类各踩过一次)

**a. UTF-8 BOM**:
Windows 记事本保存的 HTML 默认带 `EF BB BF` 三个 BOM 字节。
Nginx 反代 `sub_filter '</head>' '$canvas_autoheight</head>'` 锚点要的是字面 `</head>`。
BOM 把 `<!DOCTYPE html>` 的 `<!` 推到了字节流的 3 字节之后, sub_filter 看到的是 `EF BB BF <!DOCTYPE...` 而不是 `<!DOCTYPE ...`, 所有 `</head>` 锚点**都错位**——注入位置不可预测。

**b. 缺 `<!DOCTYPE html>`**:
matplotlib + 自拼 HTML 模板如果没写 `<!DOCTYPE html>`, 浏览器进 quirks mode——
所有 `flex` 容器变块级, `grid` 网格塌成单列, 雷达图和词云在 iframe 里完全失真。
本来雷达图是"圆形八边形", quirks mode 下变成"挤到左上角"。

**c. 缺 `</html>`**:
agent 在调试时 `<body>` 后面忘记写闭合或写到一半 SIGTERM—— 文件截断。
Nginx `sub_filter` 锚点 `</head>` 在被截 HTML 里找不到或重复, 注入位置漂移。

**d. 内容太短**:
`generate_profile.py` 写到一半被杀, 产物只有 200 字节, 整页就 `<html>...</html>` 三行。
即使发布也"看起来空白", 这是"silent fail" 的最坏情况——加了校验就 fail-fast。

### 解决

`publish_to_canvas.py` 4 条都要 check:

```python
- raw[:3] == b'\xef\xbb\xbf'                                    → reject
- DOCTYPE 存在 ( re.search(r'<!DOCTYPE\s+html', text, re.I) )   → reject
- </html>  存在 ( re.search(r'</html>', text, re.I) )           → reject
- len(raw) > 200 字节                                           → reject (过短)
```

任一不过, 整条 reject, exit=3 EX_DATAERR。

### 脚本报错形态

```
[4/9] HTML 含 UTF-8 BOM. Nginx sub_filter 锚 </head> 会错位. 请以 UTF-8 无 BOM 重新保存.
[4/9] HTML 缺 <!DOCTYPE html> 声明 (浏览器会进 quirks mode, CSS flex/grid 失真)
[4/9] HTML 缺 </html> 收尾标记 (Nginx sub_filter 注入锚点可能错位)
[4/9] HTML 过短 (37 字节), 疑似生成未完成
```

---

## 5. 同一候选人同一 ID 必须有去覆盖策略

### 事故复盘

HR 让 agent 重新生成"员工1"画像 (因为来源数据更新), agent 直接 cp 覆盖了 `profile-yuangong1/index.html`。
第二天复盘"为什么 1 周前的版本没了, 我对比一下"——没了。没有 version control, 没有备份。

### 解决

`publish_to_canvas.py` 默认**拒绝覆盖**:

```
[8/9] 目标已存在: /.../profile-yuangong1/index.html. 重发同名 ID 需要显式 --force
```

要覆盖**必须显式传 `--force`**:

```bash
python3 publish_to_canvas.py profile-yuangong1-v2.html profile-yuangong1 --force
```

或者**用版本号 ID**:

```
profile-yuangong1          # 第一次生成
profile-yuangong1-v2       # 重生成时加后缀
profile-yuangong1-v3       # ...
```

旧 ID 留在文件系统里不删, 供追溯——Canvas 路由读谁由 `[embed ref=...]` 或浏览器最近 open 决定。

> agent 在 audit-by-date 类任务里**应该**用 ID 命名空间区分 (如 `profile-yuangong1-2026-07-11`)
> —— Canvas 路由对 namespace 不敏感, `[A-Za-z0-9._-]+` 全包。

---

## 6. `<id>` 长度 ≤ 80 + 不能以 `.` 开头 + 不能含 `..` + 不能是保留字

### 事故复盘 (路径穿越 + nginx URL 长度截断)

a. agent "聪明地"用 `id=../../../etc/passwd` 想"打通" 边界——
   文件传到 `documents/../../../etc/passwd/index.html`, resolve 后逃出 canvas root。
   即使本 profile 没真的传到 /etc, 也构成 symlink attack 起点。
b. 用户传了一个 200 字符的 ID (用 `;base64,binary-data` 当 ID 想"加点 marker")——
   nginx 默认 `large_client_header_buffers 8 8k` 可能够, 但 `proxy_pass` 把 URL
   转给 gateway, gateway 反过来 parse 时可能在 200 字符左右截。
c. `id=documents`——文件会落到 `documents/documents/index.html`, 与 Canvas 路由
   `documents/<id>/` 拼出来找不到结构, 实际上还会**自己进自己子目录**——死循环。

### 解决

```python
- len(id) > 80            → reject (nginx/CDN URL 长度友好上限)
- id.startswith('.')      → reject (路径穿越防御)
- '..' in id              → reject (路径穿越防御)
- id in {'documents', '.', '..', ''} → reject (Canvas 路由保留字)
```

再加一道事后 resolve 检查: 把拼出来的 `<canvas_root>/documents/<id>/index.html` resolve,
**不在 canvas_root 内就 reject** (symlink attack)。

### 脚本报错形态

```
[3/9] id 长度 81 > 限 80 (nginx/CDN URL 长度友好上限)
[3/9] id '.hidden' 不能以 '.' 开头 (路径穿越防御)
[3/9] id '../etc' 不能含 '..' (路径穿越防御)
[3/9] id 'documents' 是 Canvas 保留字, 不可用
```

---

## 7. 落盘要 atomic (tempfile + rename)

### 事故复盘

agent 直接 `shutil.copy`——如果 `fsync` 没刷盘就被 SIGKILL, 目标文件是**半截**, 浏览器
拿到残缺 HTML 还是 200 但内容错位, 比 404 还难诊断。

### 解决

```python
fd, tmp = tempfile.mkstemp(prefix=f".{id}.", suffix=".staging", dir=parent_dir)
with os.fdopen(fd, "wb") as f:
    f.write(bytes); f.flush(); os.fsync(f.fileno())
os.replace(tmp, target)   # rename(2) 在同一文件系统下是 atomic
```

落盘后 read-back 验证字节级一致, 不一致就 fail + exit 4。

---

## 8. `[embed ref="..."]` 在 WebChat 不渲染 · 但仍要发

### 事故复盘

2026-07-11: HR 通过 WebChat 让 agent 发候选人画像, agent 输出:

```
[embed ref="profile-yuangong1" type="canvas/document" url="..."]
```

WebChat 直接显示 `[embed ref=...]` 原字符串——看起来像"渲染失败"。
agent 以为是 bug, 反复重新发布, 还是一样。

### 根因 (Canvas 插件的 native-only 设计)

`[embed ref=...]` 是 `pluginSurfaceUrls.canvas` + `node.pluginSurface.refresh`
协议的**客户端解析指令**, 只有 paired native app (iOS / Android / macOS) 能识别。
WebChat 这条聊天通道**不解析 ref**——不论发布是否成功, WebChat 都显示原始 token。

### 解决

这不是 bug, 也不是发布要解决的问题。但文档要讲清:

- **WebChat 用户体验**: 看不到图像, 只能看到 `[embed ref=...]`。
  看到 token 出现 = 已经在 Canvas 上挂了, 但要本机浏览器才能看图。
- **企业内 / 教程写作**: 提示 HR "你打开 Safari/Edge 输入这个 URL 看图"。
- **特殊 trick**: HR 把 `[embed ref=...]` 改写成绝对 URL token 推给 Safari——但本 skill
  默认行为就是"token 在, 文档在, 看图另开浏览器", 不要绕。

### 脚本报错形态 (没有 — 永远不会因为这条报错)

本节作为 reference 写在 SKILL.md / 帮 Agent 理解"为什么发了 [embed] 但 WebChat 没图"。

---

## 9. 浏览器直接打开 18790 会被 Bearer 拦 · 用 18999 反代

### 事故复盘

2026-07-11: HR 让 agent 发 URL `http://127.0.0.1:18790/__openclaw__/canvas/...`,
浏览器打开 → 401 Unauthorized (Bearer token 缺失)。

Gateway 默认 `Authorization: Bearer <token>` 拦所有 `/__openclaw__/canvas/**` 路径。
HR 没法自己手动加 token (她不知道 token)。

### 解决

本次同步建了 Nginx 反代 `127.0.0.1:18999`:
- 自动注入 `Authorization: Bearer <token>` 头
- 自动注入 adaptive-height 的 `</head>` 后 JS/CSS

HR 在浏览器里用 18999 端口:

```
http://127.0.0.1:18999/__openclaw__/canvas/documents/profile-yuangong1/index.html
```

(SSH 隧道映射 `ssh -p 23 -L 18999:127.0.0.1:18999 ...`)

`publish_to_canvas.py` 落盘后输出会**主动打印这俩 URL**, HR 直接复制粘贴:

```
[ok]   local:    /root/.openclaw-hr/canvas/documents/profile-yuangong1/index.html
  size:     200510 bytes
  nginx:    http://127.0.0.1:18999/__openclaw__/canvas/documents/profile-yuangong1/index.html   (推荐)
  gateway:  http://127.0.0.1:18790/__openclaw__/canvas/documents/profile-yuangong1/index.html   (需 Bearer)
```

---

## 10. ASCII 别名映射约定 (本 skill)

本 skill `generating-candidate-profiles` 默认约定, **新候选人首次发布时按本表**取别名:

| 中文姓名 | ASCII 别名 | 备注 |
|---|---|---|
| 员工1 | `profile-yuangong1` | 现有 |
| 其他新人 | `profile-<pinyin-no-tones>` | 例: `profile-yuangong3` |

命名规则:

- **pinyin without tones** + ASCII 短横线
- **禁止** 中文 / 全角 / emoji / 空格 / 引号
- 多重名场景加 `-c01` `-c02` 后缀

如要扩展, 在本表追加一行——本 skill 不另存别名数据库, 全靠文档约定。
