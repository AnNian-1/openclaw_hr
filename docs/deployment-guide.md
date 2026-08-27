# HCM 入职管理系统 — 部署指南

> 本文档面向组员，指导从零部署 HCM 系统和 OpenClaw HR 数字员工。

---

## 一、环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| **Python** | 3.11+ | 推荐 3.13（miniconda3） |
| **Node.js** | 22.16+ | OpenClaw 强制要求 ≥22.16.0 |
| **npm** | 10+ | 随 Node.js 安装 |
| **Git** | 2.30+ | 用于克隆仓库 |
| **miniconda** | 最新 | Python 环境管理（可选但推荐） |

---

## 二、获取项目文件

从负责人处拷贝整个项目目录到本机





---

## 三、Node.js 22 安装

如果本机 Node.js 版本低于 22.16：

```bash
# 下载 Node.js 22.16
mkdir -p ~/.local/node
cd ~/.local/node
curl -LO https://npmmirror.com/mirrors/node/v22.16.0/node-v22.16.0-linux-x64.tar.xz
tar -xf node-v22.16.0-linux-x64.tar.xz
mv node-v22.16.0-linux-x64 node-22

# 添加到 PATH（写入 ~/.bashrc）
echo 'export PATH="$HOME/.local/node/node-22/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 验证
node --version  # 应显示 v22.16.0
```

---

## 四、Python 环境

### 方案 A：使用 conda（推荐）

```bash
# 创建专用环境
conda create -n openclaw-hr python=3.13 -y
conda activate openclaw-hr

# 安装 HCM 后端依赖
cd ~/openclaw-hr/.openclaw-hr/hcm/backend
pip install -r requirements.txt
```

### 方案 B：使用系统 Python

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm/backend
pip install -r requirements.txt
```

### requirements.txt 内容

```
fastapi==0.115.12
uvicorn==0.34.3
sqlalchemy==2.0.41
pydantic>=2.12
python-multipart==0.0.20
websockets==15.0.1
```

---

## 五、环境变量配置

⚠️ **这一步必须手动完成**，`env.sh` 不在 Git 仓库中（被 `.gitignore` 排除）。

```bash
cd ~/openclaw-hr/.openclaw-hr
cp env.sh.example env.sh  # 如果有模板；否则手动创建
```

### 必须配置的变量

编辑 `env.sh`，确保以下变量正确：

```bash
# ── 路径（根据实际安装位置调整）──────────────────
export OPENCLAW_STATE_DIR="$HOME/openclaw-hr/.openclaw-hr"
export OPENCLAW_CONFIG_PATH="$HOME/openclaw-hr/.openclaw-hr/config/openclaw.yaml"
export OPENCLAW_HR_BIN="$HOME/openclaw-hr/.openclaw-hr/install/node_modules/.bin/openclaw"

# ── PATH ──────────────────────────────────────
export PATH="$HOME/.local/node/node-22/bin:$HOME/openclaw-hr/.openclaw-hr/install/node_modules/.bin:$HOME/openclaw-hr/.openclaw-hr/node_modules/.bin:$PATH"

# ── LLM API Keys（向负责人索取）────────────────
export DEEPSEEK_API_KEY="sk-..."
export DASHSCOPE_API_KEY="sk-..."
export VOLCANO_ENGINE_API_KEY="ark-..."
export XIAOMI_API_KEY="tp-..."

# ── 飞书配置 ──────────────────────────────────
export FEISHU_APP_ID="cli_..."
export FEISHU_APP_SECRET="..."

# ── Gateway Token（首次使用时生成）──────────────
export OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
```

### 加载环境变量

```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
```

---

## 六、openclaw.yaml 路径修正

如果项目不在 `$HOME/openclaw-hr/` 目录下，需要修改配置文件中的路径：

```bash
cd ~/openclaw-hr/.openclaw-hr/config

# 查看需要替换的路径
grep -n "/root/" openclaw.yaml

# 批量替换（将 /root/ 改为你的 HOME 目录）
sed -i "s|/root/.openclaw-hr|$HOME/openclaw-hr/.openclaw-hr|g" openclaw.yaml
```

---

## 七、OpenClaw 依赖安装

```bash
cd ~/openclaw-hr/.openclaw-hr
npm install

# 安装 lobster 插件（必须与 openclaw 版本匹配）
npx openclaw plugin install @openclaw/lobster@2026.5.12 --force
```

---

## 八、HCM 系统初始化

### 8.1 安装前端依赖

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm/frontend
npm install
```

### 8.2 初始化数据库

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm/backend
python seed.py
```

输出示例：
```
✅ 导入 guochao (guochao) — 运营工程师 30K
✅ 导入 leiwu (leiwu) — 后端开发工程师 18K
✅ 导入 lisi (lisi) — 人工智能算法工程师 25K
✅ 导入 lixin (lixin) — 数据标准岗位 8K
✅ 导入 zhanglei (zhanglei) — 后端工程师 32K
🎉 完成！共导入 5 位候选人
```

> `seed.py` 从 `workspace-onboarding/stub-state/` 读取 JSON 数据导入 SQLite。
> 数据库文件自动生成在 `hcm/hcm.db`。

---

## 九、启动服务

### 一键启动

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm
bash start.sh
```

### 分别启动（调试用）

```bash
# 终端 1：后端
cd ~/openclaw-hr/.openclaw-hr/hcm/backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 终端 2：前端
cd ~/openclaw-hr/.openclaw-hr/hcm/frontend
npm run dev
```

### 启动 OpenClaw Gateway（可选）

```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
openclaw gateway run
```

---

## 十、访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| **HCM 看板** | http://localhost:5173 | Vue 3 前端 |
| **HCM API** | http://localhost:8000 | FastAPI 后端 |
| **Swagger 文档** | http://localhost:8000/docs | API 交互文档 |
| **OpenClaw Gateway** | http://localhost:18790 | Agent 网关 |

---

## 十一、项目结构速查

```
.openclaw-hr/
├── hcm/                          ← HCM 系统
│   ├── backend/                  ← FastAPI 后端
│   │   ├── main.py               ← 入口（CORS、路由注册、WebSocket）
│   │   ├── models.py             ← SQLAlchemy 3 张表
│   │   ├── schemas.py            ← Pydantic 校验
│   │   ├── database.py           ← SQLite 连接
│   │   ├── routers/
│   │   │   ├── candidates.py     ← 候选人 CRUD
│   │   │   └── reviews.py        ← Review 管理
│   │   ├── websocket.py          ← WebSocket 广播
│   │   ├── seed.py               ← 数据导入脚本
│   │   └── requirements.txt
│   ├── frontend/                 ← Vue 3 前端
│   │   ├── src/components/       ← 看板组件
│   │   ├── src/stores/           ← Pinia 状态管理
│   │   ├── src/composables/      ← WebSocket composable
│   │   ├── src/types/            ← TypeScript 类型
│   │   ├── vite.config.ts        ← 代理配置
│   │   └── package.json
│   ├── start.sh                  ← 一键启动脚本
│   └── hcm.db                    ← SQLite 数据库（自动生成）
├── env.sh                        ← 环境变量（不在 Git 中）
├── config/openclaw.yaml          ← OpenClaw 主配置
├── hr-agents/hr-agents.yaml      ← Agent 定义
├── workspace-onboarding/         ← 入职 Agent 工作空间
├── workspace-recruitment/        ← 招聘 Agent 工作空间
└── workspace-training/           ← 培训 Agent 工作空间
```

---

## 十二、常见问题

### Q1: `openclaw` 命令找不到
```bash
# 确认 PATH 包含 node_modules/.bin
echo $PATH | grep openclaw
# 或直接用完整路径
$HOME/openclaw-hr/.openclaw-hr/install/node_modules/.bin/openclaw --version
```

### Q2: Node.js 版本不够
```bash
node --version
# 如果低于 v22.16.0，按第三节重新安装
```

### Q3: `seed.py` 报路径找不到
确保 `workspace-onboarding/stub-state/` 目录存在且有数据：
```bash
ls ~/openclaw-hr/.openclaw-hr/workspace-onboarding/stub-state/
# 应有 guochao/ leiwu/ lisi/ lixin/ zhanglei/ 等目录
```

### Q4: 端口被占用
```bash
# 查看占用
lsof -ti:8000
lsof -ti:5173

# 杀掉占用进程
kill $(lsof -ti:8000) 2>/dev/null
```

### Q5: 前端代理报错
确认后端已启动且在 8000 端口运行：
```bash
curl http://localhost:8000/api/health
# 应返回 {"ok":true,"service":"hcm"}
```

### Q6: Gateway 启动失败 — API Key 缺失
检查 `env.sh` 中的 API Key 是否已取消注释并填写：
```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
echo $DEEPSEEK_API_KEY  # 不应为空
```

### Q7: lobster 插件版本不匹配
```bash
# 查看当前版本
openclaw plugin list

# 强制安装匹配版本
npx openclaw plugin install @openclaw/lobster@2026.5.12 --force
```

---

## 十三、关键配置变更记录

以下是部署过程中修正的配置问题，新环境部署时需注意：

| 问题 | 修正方式 |
|------|---------|
| `env.sh` 中路径指向 `$HOME/.openclaw-hr` | 改为 `$HOME/openclaw-hr/.openclaw-hr` |
| `openclaw.yaml` 中硬编码 `/root/` 路径 | `sed` 替换为实际 HOME 路径 |
| `env.sh` 中 API Key 被注释 | 取消注释并填入实际 Key |
| lobster 插件版本过高（v2026.7.1） | 降级安装 v2026.5.12 |
| Node.js 版本不够（需 ≥22.16） | 手动下载安装 22.16.0 |
| Gateway systemd 服务缺少环境变量 | 改用 `source env.sh && openclaw gateway run` 手动启动 |
| `auth-profiles.json` 缺失 | 手动创建空 JSON `{}` |
| `openclaw.yaml` 中 `toolCalling` 字段不识别 | 删除该字段（2026.5.12 不支持） |
