# AI HR 数字员工「小慧」· 学员使用指南

> 这是 OpenClaw AI HR 课程 Lesson 2 交付的完整 profile——一套可直接运行的多 Agent AI HR 数字员工系统「小慧」。本指南讲清楚：拿到这个 profile 之后，如何在你自己的机器上把它跑起来、并通过对话使用它。

---

## 一、这是什么

「小慧」是一套多 Agent AI HR 数字员工系统，由 6 个 Agent 协同构成，覆盖招聘、入职、培训、绩效、行政员工关系五大人力资源职能：

| Agent | 角色 | 能力（Skill 数）|
|-------|------|----------------|
| `router` | 总控调度 | 统一入口，把任务路由给对的子 Agent（不配 Skill）|
| `recruitment` | 招聘子 Agent | 简历解析、评分排序、画像、人才库检索、面试纪要（12）|
| `onboarding` | 入职子 Agent | 入职流程编排、定时跟进、进度看板（3）|
| `training` | 培训子 Agent | 按主题一次产出全套培训物料（2）|
| `performance` | 绩效子 Agent | 360 反馈聚合与可视化（2）|
| `er-admin` | 行政子 Agent | HR 政策答疑、HR 月报自动生成（2）|

你只需对「小慧」说自然语言任务，`router` 会判断领域、分发给对口的子 Agent，子 Agent 调用自己的 Skill 完成工作。全系统共 21 个业务 Skill。

---

## 二、前提条件

在开始之前，你的机器上需要准备好：

1. **已安装 OpenClaw**（本 profile 不含 OpenClaw 本体）。确认 `openclaw --version` 能正常输出。
2. **Python 3**、**Node.js**、**bash** —— Skill 脚本依赖（OpenClaw 运行本身已带 Node）。
3. **两个 LLM Provider 的 API Key**：
   - **DeepSeek**（主模型）—— 申请：https://platform.deepseek.com
   - **阿里云百炼 DashScope**（fallback 模型 + 向量检索）—— 申请：https://bailian.console.aliyun.com

---

## 三、安装与配置（5 步）

### 步骤 1 · 放置 profile

把本 profile 目录放到你用户主目录下，命名为 `.openclaw-hr`：

```bash
# 假设你解压/拿到的目录叫 xiaohui-ai-hr
mv xiaohui-ai-hr ~/.openclaw-hr
```

> 建议就放在 `~/.openclaw-hr`——env.sh 默认按这个路径写。放别处也行，但要自己同步改 env.sh 里的 `OPENCLAW_STATE_DIR`。

### 步骤 2 · 运行 setup.sh 改写路径

profile 里有一些打包时的本机绝对路径，需要改成你这台机器的。在 profile 根目录执行：

```bash
cd ~/.openclaw-hr
bash setup.sh
```

它会自动把所有旧路径改写成你的实际路径，并建好运行期空目录。可重复运行。

### 步骤 3 · 填入你的 API Key

编辑 `env.sh`，把 3 个占位符替换成你自己的值：

```bash
# 用任意编辑器打开 ~/.openclaw-hr/env.sh
export OPENCLAW_GATEWAY_TOKEN="..."   # 自己设一个随机字符串，如 openssl rand -base64 32 的输出
export DEEPSEEK_API_KEY="sk-..."      # 你的 DeepSeek Key
export DASHSCOPE_API_KEY="sk-..."     # 你的阿里云百炼 Key
```

> 明文 Key 只存在 env.sh 这一个文件里——`openclaw.yaml` 里只用 SecretRef 引用变量名，不存明文。这是有意的安全设计。

### 步骤 4 · 安装 Python 依赖

部分 Skill 的脚本（评分、人才库、绩效聚合、月报、培训配图）依赖几个 Python 包：

```bash
python3 -m pip install -r ~/.openclaw-hr/requirements.txt
```

> 面试纪要的录音转写（`transcribing-interviews` Skill）依赖 `faster-whisper`，已包含在 requirements.txt 里。若你想把 ASR 装在独立虚拟环境，见下方第六节。

### 步骤 5 · 加载环境并启动

```bash
source ~/.openclaw-hr/env.sh
openclaw gateway run        # 启动 Gateway（保持这个终端开着）
```

Gateway 起来后，另开一个终端，确认健康：

```bash
source ~/.openclaw-hr/env.sh
curl http://127.0.0.1:18790/health     # 返回正常即 OK
```

---

## 四、怎么用——与「小慧」对话

「小慧」的用法就是：**对总控 `router` 说一句自然语言任务**，它会自动判断该谁干、分发下去。

```bash
source ~/.openclaw-hr/env.sh

# 例 1：让招聘子 Agent 干活
openclaw agent --agent router -m "帮我把 inbox 里的简历批量筛一遍、排个序"

# 例 2：人才库检索
openclaw agent --agent router -m "从人才库里找几个和张磊背景相似的候选人"

# 例 3：HR 政策答疑
openclaw agent --agent router -m "员工问年假到年底没休完怎么办？"

# 例 4：生成 HR 月报
openclaw agent --agent router -m "出一份这个月的 HR 月报"
```

`router` 判断领域 → 路由到对应子 Agent → 子 Agent 自己读取相应 Skill 的 `SKILL.md`、执行脚本 → 把结果给你。

你也可以直接对某个子 Agent 说话，跳过路由：

```bash
openclaw agent --agent recruitment -m "把张磊的二面录音整理成面试纪要"
```

---

## 五、6 个 Agent 与 21 个 Skill 速览

- **recruitment（招聘）**：`office-to-md-v2`、`parsing-resumes`、`auditing-extraction`、`filtering-sensitive-fields`、`scoring-candidates`、`auditing-numbers`、`generating-candidate-profiles`、`ingesting-talent-pool`、`searching-talent-pool`、`explaining-similarity`、`transcribing-interviews`、`generating-minutes`
- **onboarding（入职）**：`running-onboarding-workflow`、`running-onboarding-review`、`generating-onboarding-dashboard`
- **training（培训）**：`generating-training-materials`、`generating-training-figures`
- **performance（绩效）**：`aggregating-360-feedback`、`generating-360-dashboard`
- **er-admin（行政）**：`answering-hr-policy-questions`、`generating-monthly-report`
- **router（总控）**：无 Skill，只做调度

每个 Skill 的 `SKILL.md` 里写清了它做什么、何时用、怎么用。各子 Agent 工作区 `workspace-<id>/skills/` 下可逐个查看。

---

## 六、面试纪要功能的额外说明（ASR）

`transcribing-interviews` Skill 把面试录音转成文字，用的是 `faster-whisper`。两种装法：

- **简单做法**：已在步骤 4 用 requirements.txt 装进了系统 Python，直接可用。
- **独立虚拟环境**（推荐，避免污染系统 Python）：

  ```bash
  python3 -m venv ~/.openclaw-hr/venv-asr
  ~/.openclaw-hr/venv-asr/bin/pip install faster-whisper numpy
  ```

  之后转写脚本用 `--venv ~/.openclaw-hr/venv-asr` 参数即可指向它。

首次运行会自动下载 faster-whisper 模型（默认 `small`），需要联网，请耐心等待。

---

## 七、目录结构说明

```
~/.openclaw-hr/
├── env.sh                环境变量（API Key 在这里填）
├── setup.sh              一次性路径配置脚本
├── requirements.txt      Python 依赖
├── README.md             本指南
├── config/openclaw.yaml  系统配置（6 Agent、权限、模型、Cron 等）
├── cron/                 定时任务配置（月报、入职跟进等）
├── workspace-router/     总控 Agent 的人设文件
├── workspace-recruitment/  招聘子 Agent：人设 md + 12 Skill + 数据资产 + 产出样例
├── workspace-onboarding/   入职子 Agent
├── workspace-training/     培训子 Agent
├── workspace-performance/  绩效子 Agent
├── workspace-er-admin/     行政子 Agent
├── agent-dirs/           各 Agent 的运行配置
├── hr-agents/ flows/ settings/ hooks/   系统辅助配置
└── memory/ logs/ sessions/ agents/      运行期目录（首次运行自动重建）
```

每个 `workspace-<id>/` 下都有 `SOUL.md`（人格与边界）、`AGENTS.md`（工作流）、`TOOLS.md`（工具用法）等人设文件，以及 `skills/` 技能目录。

---

## 八、注意事项与故障排查

- **profile 不含 OpenClaw 本体**——你必须先自行安装好 OpenClaw。
- **运行记忆已清空**——交付的 profile 是干净初始状态，没有历史会话和记忆，你从零开始用。
- **没跑 setup.sh 就启动**会因路径错乱报错——务必先执行步骤 2。
- **Gateway 起不来 / 工具报 `gateway closed`**：确认 `openclaw gateway run` 那个终端还开着、`env.sh` 已 source、端口 18790 没被占用。
- **Skill 脚本报缺包**：回到步骤 4 装 Python 依赖。
- **API 调用失败**：检查 env.sh 里的 Key 是否填对、账户是否有额度。
- **首次跑面试纪要慢**：在下载 ASR 模型，属正常。

---

## 九、关于数据

本 profile 内所有 HR 数据——简历、候选人、360 反馈、政策文档、月报数据——**全部是教学模拟数据**（如候选人「张磊」是虚构人物）。绩效、简历等是法律敏感的真实人事数据，课程不使用、也不应使用真实人事数据。

把「小慧」用到真实业务时，请替换为你公司自己的数据，并结合所在法域的法规与公司法务意见，确认合规边界。

---

祝使用顺利。把「小慧」跑起来，就拥有了一个能听懂人话、会自己调用技能、能合规干活的 AI HR 数字员工。
