# 候选人画像设计细则

> generating-candidate-profiles Skill 的画像区块级细则。SKILL.md 在需要时引用本文件。
> 字段标准对齐 `candidate-profile-schema.md`（招聘子 Agent 数据资产）。

## 目录

- 1. 数据源结构
- 2. 七区块构成
- 3. 三个关键设计决策
- 4. 合规红线：哪些字段不进画像
- 5. 生成器脚本的 CLI 约定

## 1. 数据源结构

画像的数据源是 `scoring-candidates` 产出的 ranking JSON（如 `ranking-后端开发.json`）。
它对一个岗位下的全部候选人，各存了一份 `parsed`（简历解析数据）和一份 `score`（评分数据）：

```
ranking JSON
├── ranking[]            # 排序结果，每条含 name / suggested_action（建议处置）
└── details[]            # 每个候选人的完整数据
    ├── parsed           # parsing-resumes 的产出：基础信息 / education /
    │                    #   work_experience / skills / total_experience_years ...
    └── score            # scoring-candidates 的产出：jd_match_score（综合分）/
                         #   dimension_scores（8 维度分）/ overall_rating（评级）/
                         #   highlights / concerns / hard_issues / score_reasoning
```

画像生成器按「候选人姓名」从 `details` 里定位到那个人，再从 `ranking` 里取他的
`suggested_action`。**画像只忠实呈现这两处数据，不新增、不加工、不编造任何字段值。**

## 2. 七区块构成

画像由七个区块组成，每个区块对齐 schema 的字段组、回答 HR 的一个决策问题：

|| # | 区块 | 数据来源 | 呈现形式 | 回答的问题 |
||---|------|---------|---------|-----------|
|| 1 | 基本信息卡 | parsed 基础信息 | 顶部蓝色信息卡 | 这是谁、要什么岗、要多少钱 |
|| 2 | 综合评级横幅 | score 综合分+评级 + ranking 建议处置 | 信息卡右侧大字横幅，A/B/C/D 配色 | 总体该不该面 |
|| 3 | 8 维度能力雷达图 | score `dimension_scores`（8 维各 1-5 分）| matplotlib 极坐标雷达图 | 能力结构什么样 |
|| 4 | 与 JD 匹配度对比 | 综合分 vs 岗位初筛基线 60 | HTML 进度条 | 够不够初筛线 |
|| 5 | 工作经历时间线 | parsed `work_experience[]` | HTML+CSS 竖向时间轴 | 职业路径怎么走的 |
|| 6 | 技能词云 | parsed `skills[]` | matplotlib 标签云 | 核心技能是什么 |
|| 7 | 亮点·顾虑·硬伤 | score `highlights`/`concerns`/`hard_issues` | 三栏卡片（绿/橙/红）| 强在哪、弱在哪、有没有硬伤 |

## 3. 三个关键设计决策

**决策一 · 图表 matplotlib 渲染 + base64 内嵌，HTML 单文件。**
雷达图和技能词云不走 Chart.js / ECharts 前端图表库——前端库要么依赖 CDN（断网就空），
要么要打包多文件。改用 matplotlib 在 Python 端把图渲染成 PNG，base64 编码内嵌进
`<img src="data:image/png;base64,...">`。结果是画像 HTML 是**一个自包含单文件**，
离线、跨时间都能完整打开。代价是文件偏大（约 150-200KB），对单份画像可接受。

**决策二 · 8 维度雷达图用固定轴序。**
8 个维度（专业技能/经验匹配/沟通/逻辑/学习力/抗压/价值观/协作）按固定顺序绕一圈排。
雷达图多边形形状会随轴序变化，**只有所有画像轴序一致，跨候选人比轮廓才有意义**。
雷达图擅长「整体轮廓快速感知」，不擅长「精确读数」——所以画像把雷达图旁边再放一条
维度分条（条形图），雷达图给轮廓、分条给精确值，两者互补。

**决策三 · 技能用「词云」不用「熟练度条形图」——因为数据真实性。**
ranking JSON 的 `skills` 是纯技能名（`"Java"`、`"Go"`），没有统一的熟练度标注。
要画「精通/熟练/了解」三档条形图，就得让脚本去猜每项技能的熟练度——这是编造。
词云的字号只编码「技能在简历里列出的先后顺序」（越靠前=候选人优先列出的核心技能，
这是简历里真实存在的排序信号），不需要任何熟练度数据。
**可视化形式必须迁就真实数据的粒度，不为「图好看」编造数据里没有的维度。**

## 4. 合规红线：哪些字段不进画像

ranking JSON 的 `parsed` 里可能带 `出生年月` / `性别` / `政治面貌` / `婚育` 等字段——
这些是候选人数据资产里允许记录的信息（HR 做性别比例统计等需要）。但**画像是展示给
用人方看的页面**，schema §9（依据个保法 24 条 / 就业促进法 26-31 条）规定：

> 年龄 / 出生日期 / 性别 / 婚育 / 政治面貌 / 户籍·籍贯 / 民族 / 健康状况
> —— 这些字段**绝不能渲染进画像**。

原因：画像里出现「性别 男 / 年龄 38」，看画像的人会不自觉地把它当筛选依据，
构成就业歧视风险。画像七区块的设计本身就只取「岗位相关」字段——
基础信息卡只展示目标岗位、薪资、城市、到岗、学历、年限，不展示任何身份属性。
`validate_profile_html.js` 会扫产出 HTML，发现合规字段被渲染即报错退出。

## 5. 生成器脚本的 CLI 约定

`generate_profile.py` 的命令行约定（与 office-to-md / parsing-resumes 脚本同一套）：

- 入口：`python3 generate_profile.py <ranking.json> <候选人姓名> <输出 HTML 路径>`
- 退出码：成功 `0`；参数数量错 `1`；候选人在 ranking JSON 里找不到 `2`。
- stdout 输出四阶段执行痕迹（`[1/4] 数据载入 ... [4/4] HTML 画像已生成`），
  Agent 调 `exec` 后读 stdout 拿生成信息、靠退出码判断成败。
