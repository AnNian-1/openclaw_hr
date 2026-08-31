---
name: generating-candidate-profiles
description: Render a single candidate from a ranking JSON into a visual, self-contained HTML candidate profile. Use this skill whenever a scored candidate needs to become an HR-readable visual profile — a seven-region page with an 8-dimension capability radar chart, a work-history timeline, and a skill cloud. Takes the parsed resume data plus the scoring result that scoring-candidates already produced; it does not parse resumes, score candidates, or audit numbers — it only visualizes data that already exists. Charts are matplotlib-rendered and base64-embedded so the HTML opens offline with no external dependency. The companion publish step (publish_to_canvas.py) copies the validated HTML into OpenClaw's Canvas host directory so HR can open it in a browser at the nginx canvas-proxy URL (18999); the document id must be ASCII (`profile-<pinyin-no-tones>`). Never renders legally sensitive fields (age, gender, marital status, ethnicity) into the profile.
metadata:
  openclaw:
    requires:
      bins: ["python3", "node"]
---

# generating-candidate-profiles

把 ranking JSON 里某个候选人的解析数据 + 评分数据，渲染成一张图文并茂的单文件
HTML 候选人画像。

## 何时用这个 Skill

`scoring-candidates` 评完分、产出 ranking JSON 之后，需要把某个候选人的数据
变成 HR 真正能看的可视化页面时用。HR 看不懂一堆 JSON 字段——画像把这些字段
组织成「信息卡 + 雷达图 + 时间线 + 词云 + 三栏」，HR 扫一眼就有判断。

这个 Skill 只做「数据 → 可视化画像」这一件事。它**不解析简历**（那是
`parsing-resumes`）、**不评分**（那是 `scoring-candidates`）、**不核对数字真实性**
（那是 `auditing-numbers`）。它只忠实呈现 ranking JSON 里**已经存在**的数据。

## 工作流程

画像生成分两步，按顺序做：

### 第 1 步 · 生成画像

用生成器脚本，从 ranking JSON 里取某个候选人的数据，渲染成单文件 HTML：

```bash
bash scripts/recruitment-run.sh python3 skills/generating-candidate-profiles/scripts/generate_profile.py \
  <ranking.json|score.json> <候选人姓名> profile/output/profile-<候选人姓名>.html [parsed.json]
```

单份 `score_candidate` 产出也可直接喂进来（无 `details` 时会读 `parsed/<姓名>.json` 或 `scoring/clean-<姓名>.json`，或第 4 个参数）。

脚本会渲染 8 维度雷达图、技能词云（matplotlib），把图 base64 内嵌进 HTML，
产出一个自包含单文件。stdout 会打印四阶段执行痕迹，退出码 0 = 成功。

生成的硬规则（必须照做，不靠判断）：
- **画像里每个字段值都取自 ranking JSON，绝不编造。** 综合分、维度分、工作经历、
  技能——画像是「忠实呈现」，不是「另起炉灶写一份」。生成器脚本本身就保证这点。
- **合规红线字段绝不渲染进画像**：年龄、出生日期、性别、婚育、政治面貌、户籍、
  民族、健康。ranking JSON 的 `parsed` 里可能带这些字段（数据资产允许记录），
  但画像是给用人方看的展示页，渲染它们构成就业歧视风险（依据见
  `references/profile-design.md` §4）。
- **8 维度雷达图用固定轴序**。所有候选人画像维度轴序一致，跨候选人比轮廓才有意义。

七区块构成、三个设计决策、合规细则见 → `references/profile-design.md`

### 第 2 步 · 校验

生成的画像 HTML 必须用校验脚本过一遍，跑通才算合格：

```bash
node skills/generating-candidate-profiles/scripts/validate_profile_html.js \
  <profile.html> <ranking.json> <候选人姓名>
```

脚本校验：HTML 非空、七区块齐全、雷达图与词云为 base64 内嵌图、**合规红线字段
零渲染**、画像里的综合分/评级/技能数与数据源 ranking JSON 一致。退出码 0 = 通过，
1 = 不通过（会列出全部问题）。校验不通过的画像不算生成完成——按报出的问题
排查（多数是数据源不对或候选人姓名写错），修正后重跑。

### 第 3 步 · 发布到 Canvas（默认推荐）

校验通过的画像复制到 OpenClaw Canvas host 目录，让 HR 用浏览器直接看图
（不用下载、不用打开本地 HTML）：

```bash
python3 scripts/publish_to_canvas.py <profile.html> profile-<pinyin-no-tones>
```

脚本是 9 步 fail-fast 校验链，**不传合法 ASCII 别名就会报错并退出**（不会
静默发布失败的 HTML）。落盘后 stdout 会打印 nginx 18999 / gateway 18790 的可
访问 URL，HR 复制粘贴到浏览器即看。

**强约束**（必须满足，错一个都 publish 失败）：

- `<id>` 必须纯 ASCII `[A-Za-z0-9._-]+`——不能中文、emoji、全角
- 文件名自动固定为 `index.html`，**不**需要也不能改
- HTML 必须 UTF-8 无 BOM，含 `<!DOCTYPE html>` 和 `</html>` 闭合
- 路径落到 `$OPENCLAW_STATE_DIR/canvas/documents/<id>/index.html`

### HR 浏览器开图 · URL 形态警示（最容易踩坑）

`publish` 落盘成功后 stdout 会打印两条 URL，**直接复制 stdout 那行给 HR**——
不要从这文档里手动拼，手动拼接几乎一定会写错 basePath 或端口。

**正确形态**（basePath 是 `__openclaw__` —— **双下划线**夹 openclaw 全文小写）：

```text
http://127.0.0.1:18999/__openclaw__/canvas/documents/profile-zhanglei/index.html
                   ──────────
                   ↑ 双下划线 + 全小写, 这是 Canvas 路由硬编码的 basePath
```

**错误形态**（publish 校验过得了，但 HR 浏览器 404）：

```text
❌  http://127.0.0.1:18790/_openclaw_/canvas/.../index.html
    (18790 需 Bearer, HR 浏览器直接打开会 401)

❌  http://127.0.0.1:18999/openclaw/canvas/.../index.html
    (basePath 不是 openclaw —— 双下划线必须有, 改一个就 404)

❌  http://127.0.0.1:18999/_openc1aw_/canvas/.../index.html
    (字母 l 写成数字 1 —— 路由前缀 HTTP 不解码, 404)

❌  http://127.0.0.1:18999/__openclaw__/Canvas/.../index.html
    (大小写错, basePath 全小写)
```

**端口选择表**（HR 拷贝到浏览器后实际打不开时的兜底参考）：

| HR 浏览器场景 | 用哪条 URL |
|---|---|
| HR 本机直连 127.0.0.1（同台机器上） | `http://127.0.0.1:18999/__openclaw__/canvas/documents/<id>/index.html` —— 推荐, 无 Bearer |
| HR 在远程, SSH 隧道已建 | `http://127.0.0.1:18999/...` (本地端口 18999 已 tunnel) |
| HR 拿到的是 18790 端口的链接 | 提醒 HR 改用 18999, 或由 agent 在服务端补 Authorization 头 |

**章节结尾**：「publish stdout 输出的 URL 是权威版本——不要从这文档里手动拼，**直接复制 stdout 那行**」。

**为什么必须这样**：每个约束背后都对应一次具体的事故复盘（中文目录名导致
Canvas 路由 throw 400、BOM 让 Nginx sub_filter 锚点错位、目录穿越等）。完整
复盘 + ASCII 别名映射表 → `references/canvas-publishing.md`。本节负责「怎么用」，
那一节负责「为什么必须这么用」。

**`[embed ref="..."]` 在 WebChat 不渲染**：Canvas 文档是被 paired native app
（iOS/Android/macOS）解析的 chat 指令，WebChat 这条通道**只显示 token 字符串
不显示图像**。HR 看图永远是浏览器独立窗口。这一条不是 bug，本 Skill 文档
提前说清以防误诊。

**HR 看不到图的兜底**：让 HR 用浏览器直接开 nginx 反代端口（18999，已经被
`gateway-start.sh` 自动起）的 URL，publish 脚本落盘后会打印这个 URL。

## 关键规则

- 一个候选人对应一份 `profile/output/profile-<姓名>.html`。
- 图表必须 base64 内嵌——画像是单文件自包含产物，不依赖 CDN、不联网也能打开。
- 画像底部固定声明「评分仅供初筛参考，最终录用决定由人工做出」——画像帮 HR
  看清楚，不替 HR 做淘汰。这是合规边界，不要移除。
- **发布到 Canvas 时 `<id>` 必须纯 ASCII**。中文 / 全角 / emoji 在 Canvas
  host 的 `normalizeCanvasDocumentId()` 会被直接 throw，**整个发布白做**。
  约定前缀 `profile-<pinyin-no-tones>`，例：`profile-zhanglei`。重名场景加
  `-c01` / `-c02` 后缀。重发同一 id 默认需要 `--force`，防误覆盖旧版本。
  命名约定 + 事故复盘 → `references/canvas-publishing.md`。
- 数据真实性核对（评分数字逐项回溯简历原文）是 `auditing-numbers` 的事。
  本 Skill 只保证「画像忠实呈现了 ranking JSON」，不保证「ranking JSON 本身的
  数字都真」——上游数据的真实性由 `auditing-numbers` 把关。
