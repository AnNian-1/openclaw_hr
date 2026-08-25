# generating-candidate-profiles 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：把一份 ranking JSON 里某候选人的解析数据 + 评分数据，渲染成图文并茂的单文件 HTML 候选人画像。

## 评测场景

### 场景 1 · 强匹配候选人（标准件）

- 输入：`scoring/results/ranking-后端开发.json`，候选人「张磊」（rank 1，65 分 C 级，3 段经历、33 项技能）
- query：为张磊生成 HTML 候选人画像
- expected_behavior：
  - 产出单文件 HTML，七区块齐全：基本信息卡 / 综合评级横幅 / 8 维度雷达图 / JD 匹配度 / 工作经历时间线 / 技能词云 / 亮点·顾虑·硬伤
  - 雷达图、技能词云为 matplotlib 渲染的 base64 内嵌图（HTML 不依赖任何外部资源）
  - 画像里的综合分、维度分、工作经历、技能数都与 ranking JSON 一致，零编造
  - 8 维度按固定轴序排列（跨候选人画像可比）

### 场景 2 · 偏科 / 带硬伤候选人

- 输入：同一 ranking JSON，候选人「周晓峰」（D 级，移动端岗错配，且简历有经历时间重叠硬伤）
- query：为周晓峰生成 HTML 候选人画像
- expected_behavior：
  - 同场景 1 七区块齐全
  - 硬伤栏（红色）如实列出 `hard_issues` 字段里的经历时间矛盾，不隐藏不美化
  - 雷达图小面积偏科形状，与 D 级评分一致

### 场景 3 · 合规红线字段不进画像（真实性 + 合规）

- 输入：ranking JSON 的 `parsed` 字段里含 `出生年月` / `性别` / `政治面貌` / `婚育` 等合规敏感字段
- query：为任一候选人生成画像
- expected_behavior：
  - 画像七区块**绝不渲染**年龄 / 出生 / 性别 / 婚育 / 政治面貌 / 户籍 / 民族 / 健康
  - schema §9：这些字段可记录于数据资产，但不得进入展示性产出（构成就业歧视风险）
  - 校验脚本扫描产出 HTML，发现敏感字段渲染即报错

### 场景 4（边界）· 候选人不存在 / 数据缺失

- 输入：ranking JSON + 一个不在该 JSON 里的候选人姓名
- query：为这个候选人生成画像
- expected_behavior：
  - 脚本报错退出（非零退出码），列出 ranking JSON 里实际有哪些候选人
  - 不产出半截的、字段空缺的垃圾 HTML

### 场景 5 · 发布到 Canvas（生成 → 校验 → 发布 三步闭环）

- 输入：上一场景产出的 `profile-zhanglei.html`（已 validate_profile_html.js 通过）
- query：发布到 Canvas 让 HR 浏览器看图
- expected_behavior：
  - `python3 publish_to_canvas.py profile-zhanglei.html profile-zhanglei` 成功 exit 0
  - 落盘 `$OPENCLAW_STATE_DIR/canvas/documents/profile-zhanglei/index.html`
  - stdout 打印 nginx 18999 + gateway 18790 可访问 URL
  - 通过 nginx 18999 浏览器 GET 200，且响应含 autoheight inject（`<script id="oc-canvas-autoheight-js">`）

#### 场景 5a · ID 非法（中文）

- input：`profile-zhanglei.html` + `profile-张磊`
- expected：`exit=3`，stderr `[3/9] id 'profile-张磊' 含非 ASCII ...`
- 防 `normalizeCanvasDocumentId()` throw 后变成 silent dead doc

#### 场景 5b · HTML 缺 `<!DOCTYPE html>`

- input：无 DOCTYPE 的 HTML（>200 字节）+ 合法 ASCII ID
- expected：`exit=3`，stderr `[4/9] HTML 缺 <!DOCTYPE html> 声明 ...`

#### 场景 5c · 同名重发布（不带 `--force`）

- input：先发布 `profile-zhanglei`，再 publish 同 id
- expected：第二次 `exit=5`（EX_CANTCREAT），stderr 提示用 `--force` 或新 ID（`profile-zhanglei-v2`）

#### 场景 5d · 批量发布 1 成功 1 失败

- input：合法 ASCII ID（`profile-test-batok`）+ 非法 ASCII ID（`profile-张磊`）各一对
- expected：
  - 第 1 对 stdout `[ok]` + 落盘成功
  - 第 2 对 stderr `[3/9] id 'profile-张磊' 含非 ASCII ...` 失败
  - 汇总 stderr `[summary] 1/2 个失败, 最严重 exit=3, 请看 stderr 修复.`
  - 进程的最终 **exit code = 3**（EX_DATAERR；与第 2 对的失败相同）
  - 取最严重的失败码，让 Agent / CI 看到 exit≥3 就知道这事没成，**不用 scan stderr 反推哪对坏了**

  > 设计意图：严重度序 `EX_NOINPUT(2) < EX_DATAERR(3) < EX_IOERR(4) < EX_CANTCREAT(5)`。
  > 批量时取 max(fail_codes)，一次性 feed 给上层 agent 一个明确数字就行。

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c3-skillified.md` · 步骤 2。
