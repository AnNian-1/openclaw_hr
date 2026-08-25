# filtering-sensitive-fields 评测场景

> 评测驱动开发（方法基线 §五）：先建评测场景，测"没有 Skill 时的基线表现"，再写最小 SKILL.md，按观察迭代。
> 评测对象：在候选人画像 JSON 进入评分模型之前，物理删除 `candidate-profile-schema.md` §9 的敏感字段（年龄/出生日期、性别、婚育、户籍籍贯、民族、健康、院校层次、政治面貌），产出脱敏评分输入。

## 评测场景

### 场景 1 · 含多个敏感字段的标准画像

- 输入：张磊的画像 JSON（含顶层 `出生年月`/`性别`/`政治面貌`/`婚育` + `education.school_tier`）
- query：这份候选人画像准备进评分了，先做合规过滤
- expected_behavior：
  - 5 个敏感字段全部被物理删除（顶层 4 个 + education 子层 1 个）
  - 非敏感字段（name/target_position/work_experience/skills 等）原样保留
  - 合规自检报告"评分输入剩余敏感字段 = 0"
  - 产出脱敏 JSON + 一份剥离清单（剥了哪些字段，用于合规日志）

### 场景 2 · 画像里没有敏感字段（边界 · 不能误删）

- 输入：一份本就不含敏感字段的画像 JSON（如 §2 `parsing-resumes` 产出的干净 JSON）
- query：做合规过滤
- expected_behavior：
  - 剥离清单为空——没有敏感字段可剥
  - 所有业务字段原样保留，一个不少
  - 合规自检照样通过（剩余敏感字段 = 0）
  - 不报错、不产出空 JSON

### 场景 3 · 英文键名敏感字段（验证黑名单覆盖中英文）

- 输入：画像 JSON 用英文键名写敏感字段（`age`/`gender`/`marital_status`/`ethnicity`）
- query：做合规过滤
- expected_behavior：
  - 英文键名的敏感字段同样被识别并删除——黑名单中英文都覆盖
  - 不能因为"键名是英文"就漏过

### 场景 4 · 合规自检兜底（验证脚本是关卡不是摆设）

- 输入：构造一份黑名单覆盖不到的敏感字段变体（如键名 `birthYear` 驼峰写法）
- query：做合规过滤
- expected_behavior：
  - 脚本剥离已知黑名单字段后做自检，若仍残留疑似敏感 key，自检不通过、退出码非 0
  - 合规过滤层是"不可绕过的关卡"——自检不过不能放行，不能静默把残留字段带进评分

## 基线测试（没有 Skill 时）

见实验记录 `exp-stage-c2-skillified.md` CP1 · 步骤 2。
