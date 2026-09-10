# AI HR 数字员工「小慧」· 使用指南

骨架来自 OpenClaw 课程 profile，**现行配置以 2026-08 为准**（详见仓库 [`docs/项目说明.md`](../docs/项目说明.md)）。

- OpenClaw **2026.5.12**
- Gateway 主模型 **`xiaomi/mimo-v2.5-pro`**（部分招聘脚本仍调 DeepSeek API，那不是默认对话模型）
- Profile 在**本仓库** `.openclaw-hr/`，不是课程里的 `~/.openclaw-hr`
- 飞书绑定 **`er-admin`**；WebChat 绑定 **`router`**
- 月末自动月报走宿主机脚本；飞书 **HR**、WebChat、CLI 可以对话补跑。飞书非 HR 不能出月报、不能查他人工资。

---

## 一、这是什么

星型调度：WebChat → `router` → `sessions_spawn` 到五域。飞书私聊/群聊直达 `er-admin`。HCM 是独立应用（`:8000` / `:5173`），不是 Agent。

| Agent | 角色 |
|-------|------|
| `router` | WebChat 总控，只调度 |
| `recruitment` | 招聘（含邮箱收信等 13 个 Skill） |
| `onboarding` | 入职编排、review、看板 |
| `training` | 按点名生成培训物料 |
| `performance` | 360 聚合与看板 |
| `er-admin` | 政策问答；HR/WebChat/CLI 查花名册薪资、补跑月报 |
| `er-admin-cron` | 仅月报；与 er-admin 共用工作区 |
| `main` | 不作业务入口 |

---

## 二、前提

1. 已安装 OpenClaw 2026.5.12（`openclaw --version`）。
2. Node ≥ 22.16、conda 环境 `openclaw-hr`（见 `conda/environment-openclaw-hr.yml`），RAR 另需 `scripts/ensure-rar-tools.sh`。**按 Agent 的包和密钥**见仓库 [`docs/环境配置.md`](../docs/环境配置.md)。
3. 密钥在 `env.sh`（gitignore）。从 `env.sh.example` 复制，填 `OPENCLAW_GATEWAY_TOKEN`、`XIAOMI_API_KEY`、`SILICONFLOW_API_KEY`、飞书/IMA，以及脚本仍需要的 `DEEPSEEK_API_KEY` 等。yaml 只引用变量名。

---

## 三、安装

设 `$PROFILE` 为本目录（仓库里的 `.openclaw-hr`）。

```bash
cd /path/to/openclaw-hr/.openclaw-hr
export PROFILE="$PWD"
cp env.sh.example env.sh          # 填密钥；OPENCLAW_STATE_DIR 指到 $PROFILE
bash setup.sh                     # 只改课程旧路径 /Users/hsail 与 /root
# 若 yaml 里仍是 /home/yhwz/openclaw-hr，迁机时自行替换
conda env update -f conda/environment-openclaw-hr.yml
bash scripts/ensure-rar-tools.sh
source env.sh
openclaw gateway run
# 另开终端
curl -sS http://127.0.0.1:18790/health
```

HCM、Canvas：见 [`docs/项目说明.md`](../docs/项目说明.md) 第 4 节与 [`hcm/README.md`](hcm/README.md)。组员逐步命令：[`docs/deployment-guide.md`](../docs/deployment-guide.md)。

`setup.sh` **不会**改写 `/home/yhwz/openclaw-hr`。Canvas token 由 `nginx/start-canvas-proxy.sh` 从 `OPENCLAW_GATEWAY_TOKEN` 注入，不要把 token 写进 `nginx/conf/canvas-proxy.conf` 再提交。

---

## 四、怎么对话

```bash
source env.sh

openclaw agent --agent router -m "帮我把 inbox 里的简历批量筛一遍、排个序"
openclaw agent --agent router -m "从人才库里找几个和员工1背景相似的候选人"
openclaw agent --agent router -m "员工问年假到年底没休完怎么办？"
openclaw agent --agent router -m "员工1工资多少？"
openclaw agent --agent router -m "出一份 2026-07 的 HR 月报"

bash workspace-er-admin/scripts/er-admin-run.sh payroll-query --name 员工1
bash workspace-er-admin/scripts/er-admin-run.sh monthly-report --force 2026-07
```

也可 `openclaw agent --agent recruitment -m "..."` 直连子 Agent。飞书员工只应问政策；飞书 HR 可查他人工资、可出月报。

---

## 五、Skill 速览

- **recruitment**：`fetching-resumes-by-mail`、`office-to-md-v2`、`parsing-resumes`、`auditing-extraction`、`filtering-sensitive-fields`、`scoring-candidates`、`auditing-numbers`、`generating-candidate-profiles`、`ingesting-talent-pool`、`searching-talent-pool`、`explaining-similarity`、`transcribing-interviews`、`generating-minutes`
- **onboarding**：`running-onboarding-workflow`、`running-onboarding-review`、`generating-onboarding-dashboard`
- **training**：`generating-training-materials`（点名 `--only`；不要默认全套 8 份）
- **performance**：`aggregating-360-feedback`、`generating-360-dashboard`
- **er-admin**：`answering-hr-policy-questions`、`querying-employee-payroll`、`generating-monthly-report`、`ima-skill`
- **router**：无业务 Skill

面试转写是 **FunASR**（conda `funasr_me`），不是 faster-whisper。本机 ASR 尚未补测，不要用假转写冒充通过。

---

## 六、目录

```
.openclaw-hr/
├── env.sh / env.sh.example
├── setup.sh
├── config/openclaw.yaml
├── cron/jobs.json
├── conda/  scripts/  nginx/  hcm/  canvas/
├── workspace-router/  workspace-recruitment/  workspace-onboarding/
├── workspace-training/  workspace-performance/  workspace-er-admin/
├── agent-dirs/  hr-agents/
└── memory/ logs/ sessions/ agents/    # 运行时，不入库
```

每人设工作区有 `SOUL.md`、`AGENTS.md`、`TOOLS.md`、`*INTRO.md`。

---

## 七、数据

简历、360、月报 CSV、夹具候选人（员工1等）是教学/测试数据。不要当真实人事，不要编造花名册或绩效等级。把系统接到真实业务前须自行替换数据并做合规评估。

故障与迁云：[项目说明](../docs/项目说明.md)、[交接](docs/云迁移与记忆交接.md)。
