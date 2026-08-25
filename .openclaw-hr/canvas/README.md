# Canvas Hosted Documents 约定

> 这份文档面向所有把候选人画像 / 评估报告 / 任何 HTML 放进 Canvas 插件托管目录的 agent。
> 写这份是为了防止再次出现 `[embed ref=...]` 渲染不出来的诡异现象。

## 1. 物理路径与 URL

- **文件根**：`/root/.openclaw-hr/canvas/`（由 `config/openclaw.yaml` 的 `plugins.entries.canvas.config.host.root` 显式指定，写死的默认值是 `<stateDir>/canvas`）。
- **HTTP basePath**：`/__openclaw__/canvas/`（插件硬编码，不可改）。
- **Hosted document 路径模板**：`/root/.openclaw-hr/canvas/documents/<id>/index.html`。
- **对外 URL**：`http://127.0.0.1:18790/__openclaw__/canvas/documents/<id>/index.html`
  - 18790 = `gateway.port`，只 listen 127.0.0.1；外网访问需要宿主机端口映射 / 反代。

## 2. `<id>` 的硬性约束 —— 这是踩坑的根源

`normalizeCanvasDocumentId()` 只接受 `[A-Za-z0-9._-]`：

```js
// install/node_modules/openclaw/dist/server-DXKfnO2y.js
if (!/^[A-Za-z0-9._-]+$/.test(rawDocumentId)) throw new Error("canvas document id invalid");
```

**结论**：`<id>` 必须**纯 ASCII**。中文 / 全角 / emoji 都会被拒。
落到 HTTP 上时，中文 URL 在某些客户端（curl / Python `http.server` / 浏览器旧版本）会因为 raw byte 解析错而返回 400。**统一只用 ASCII 别名**。

## 3. ASCII 别名映射约定

历史上招聘 agent 用"中文候选人名"作为目录名，导致 `[embed]` 渲染不出来。**统一约定如下**：

| 中文姓名 | ASCII 别名 |
|---|---|
| 张磊 | `profile-zhanglei` |
| 周晓峰 | `profile-zhouxiaofeng` |
| 林婉清 | `profile-linwanqing`（若已占用则用 `profile-linwanqing-c01`） |
| 林雨桐 | `profile-linyutong` |
| 王浩然 | `profile-wanghaoran` |
| 郑凯文 | `profile-zhengkaiwen` |
| 陈雅琴 | `profile-chenyaqin` |
| 其他新人 | `profile-<pinyin(无声调)>`，例：`profile-lisi`、`profile-wangfang` |

> 命名规则：**pinyin without tones** + ASCII 短横线。**禁止**中文、空格、引号。

## 4. agent 写文件的标准动作

把画像 HTML 写入 Canvas host 时，**必须**走 ASCII 别名路径，**不要**自己造中文目录：

```bash
# 1. 先生成 HTML 到 workspace（任意文件名）
#    例如：/root/.openclaw-hr/workspace-recruitment/profile/output/profile-zhanglei.html

# 2. 拷到 Canvas 文档目录（id 必须 ASCII）
mkdir -p /root/.openclaw-hr/canvas/documents/profile-zhanglei
cp /root/.openclaw-hr/workspace-recruitment/profile/output/profile-zhanglei.html \
   /root/.openclaw-hr/canvas/documents/profile-zhanglei/index.html

# 3. （可选）触发 Gateway 热加载；如未热加载，手动 restart
openclaw gateway restart   # 仅当配置改动时需要；纯文件写入不需要
```

## 5. `[embed ref="..."]` 在 WebChat 里**不渲染**

`[embed ref=...]` 走的是 `pluginSurfaceUrls.canvas` + `node.pluginSurface.refresh`，**只能被 paired node（iOS / Android / macOS 原生 app）解析**。WebChat 这条聊天通道不解析 `ref`，所以在 WebChat 里看到 `[embed]` 原样输出来，**不是 bug**。

WebChat 想要看图，请直接用浏览器打开 URL：

```
http://127.0.0.1:18790/__openclaw__/canvas/documents/<id>/index.html
```

或下载 workspace 里的原始 HTML（自包含 base64，浏览器双击即可）。

## 6. Canvas host 的开关

`plugins.entries.canvas.config.host.enabled = false` 可以临时关掉 Canvas host，
不影响其他 plugin。`liveReload = false` 关掉 ws 注入，避免响应里多一段自动刷新的 `<script>`（适合一次性预览）。

配置改完后，**Gateway 会自动 hot reload**（看 `/root/.openclaw-hr/logs/gateway.log` 里的 `[reload] config hot reload applied (plugins.entries.canvas)` 行），无需手动 restart。
