# 部署指南（HCM + OpenClaw HR）

面向组员从 GitHub clone 后在本机或开发云主机拉起服务。架构与红线见 [项目说明.md](项目说明.md)。钉 OpenClaw **2026.5.12**。

下文 `$REPO` = clone 下来的仓库根，`$PROFILE="$REPO/.openclaw-hr"`。本机示例曾是 `$HOME/openclaw-hr`。

---

## 一、环境要求

| 依赖 | 说明 |
|------|------|
| Git | clone https://github.com/yhwz131/openclaw |
| Node.js | ≥ 22.16.0 |
| Python / conda | 推荐 conda 环境名 `openclaw-hr`（`conda/environment-openclaw-hr.yml`） |
| OpenClaw | 2026.5.12；Lobster 插件必须同版本 |
| unrar | `bash "$PROFILE/scripts/ensure-rar-tools.sh"`（conda-forge 无 linux-64 包） |

---

## 二、获取代码

```bash
git clone git@github.com:yhwz131/openclaw.git "$REPO"
cd "$REPO"
```

不要用 `_ref/` 或 `hr_claw_hub.tar.gz` 当现行树。会话、`env.sh`、`hcm.db` 不在 git 里，迁机另拷，见 [云迁移与记忆交接.md](../.openclaw-hr/docs/云迁移与记忆交接.md)。

---

## 三、Node.js 22

若 `node -v` 低于 22.16：

```bash
mkdir -p ~/.local/node && cd ~/.local/node
curl -LO https://npmmirror.com/mirrors/node/v22.16.0/node-v22.16.0-linux-x64.tar.xz
tar -xf node-v22.16.0-linux-x64.tar.xz
mv node-v22.16.0-linux-x64 node-22
echo 'export PATH="$HOME/.local/node/node-22/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
node --version
```

业务脚本会 source `$PROFILE/scripts/prepend-node22.sh`。

---

## 四、Python / conda

```bash
conda env update -f "$PROFILE/conda/environment-openclaw-hr.yml"
conda activate openclaw-hr
bash "$PROFILE/scripts/ensure-rar-tools.sh"
pip install -r "$PROFILE/hcm/backend/requirements.txt"
```

FunASR 用**单独**环境 `funasr_me`，见 [环境配置.md](环境配置.md)。本机面试转写仍跳过补测。

---

## 五、环境变量

`env.sh` gitignore，必须本地创建：

```bash
cp "$PROFILE/env.sh.example" "$PROFILE/env.sh"
```

至少设置（只填你自己的值，不要提交）：

- `OPENCLAW_STATE_DIR="$PROFILE"`
- `OPENCLAW_CONFIG_PATH="$PROFILE/config/openclaw.yaml"`（若你的启动方式需要）
- `OPENCLAW_GATEWAY_TOKEN`（随机串；Canvas 启动脚本注入 nginx，不要把 token 写入 `nginx/conf/canvas-proxy.conf` 再 git add）
- `XIAOMI_API_KEY`（Gateway 主模型）
- `SILICONFLOW_API_KEY`（embedding）
- `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY`（部分 Skill 脚本）
- `FEISHU_APP_SECRET`（yaml 里已有 appId 的 SecretRef）
- IMA：`IMA_OPENAPI_CLIENTID`、`IMA_OPENAPI_APIKEY`、`IMA_HR_KNOWLEDGE_BASE_ID`

```bash
source "$PROFILE/env.sh"
```

---

## 六、路径

`bash "$PROFILE/setup.sh"` 只替换 `/Users/hsail/.openclaw-hr` 与 `/root/.openclaw-hr`。

yaml、`cron/jobs.json`、nginx 日志路径里若仍是 `/home/yhwz/openclaw-hr`，换机后：

```bash
# 示例：把旧根换成新 $REPO（先确认 grep 结果再 sed）
grep -n "/home/yhwz/openclaw-hr" "$PROFILE/config/openclaw.yaml" | head
```

`openclaw config validate` 应通过。`maxChildrenPerAgent` / `runTimeoutSeconds` 只允许出现在 `agents.defaults.subagents`。

---

## 七、OpenClaw 与 Lobster

按你现有安装方式保证 `openclaw` 在 PATH。Lobster 必须 **2026.5.12**，不要装更新主版本。

```bash
openclaw --version
openclaw plugin list
```

---

## 八、HCM

```bash
cd "$PROFILE/hcm/frontend" && npm install
cd "$PROFILE/hcm/backend" && python seed.py   # 从 stub-state 灌演示人
bash "$PROFILE/hcm/start.sh"
```

新人必须先在 HCM 建档再 `run-onboarding.sh start`。小慧只 GET。详见 [hcm/README.md](../.openclaw-hr/hcm/README.md)。

`start.sh` 里后端目前 `--host 0.0.0.0`；云主机建议改成 `127.0.0.1`。

---

## 九、启动

```bash
source "$PROFILE/env.sh"
openclaw gateway run                          # 保持运行；飞书/Cron/Lobster 都在此进程
curl -sS http://127.0.0.1:18790/health
bash "$PROFILE/nginx/start-canvas-proxy.sh"   # :18999，需 Gateway
# 可选：乐奇眼镜文件接收（与 Gateway 分进程）
# bash "$PROFILE/scripts/rokid-app-ingest.sh" start
```

| 服务 | 地址 |
|------|------|
| HCM 前端 | http://127.0.0.1:5173 |
| HCM API / Swagger | http://127.0.0.1:8000 与 `/docs` |
| Gateway | http://127.0.0.1:18790 |
| 乐奇眼镜上传 | http://127.0.0.1:18791（需 `ROKID_APP_INGEST_SECRET`） |
| Canvas 反代 | http://127.0.0.1:18999 |

对话示例见 [`.openclaw-hr/README.md`](../.openclaw-hr/README.md)。**不要**对 router/飞书要月报。

---

## 十、常见问题

- **找不到 `openclaw`**：把安装目录的 `node_modules/.bin` 加进 PATH，或用你机器上的绝对路径。
- **Node 太旧**：第三节。
- **seed 找不到人**：看 `$PROFILE/workspace-onboarding/stub-state/`。
- **端口占用**：`lsof -ti:8000,5173,18790,18791,18999`。
- **前端代理失败**：后端要先在 8000 起来，`curl http://127.0.0.1:8000/api/health`。
- **Gateway 起不来**：`source env.sh`；主模型要 `XIAOMI_API_KEY`。
- **lobster 版本不对**：卸掉新版本，装与 OpenClaw 相同的 2026.5.12。
- **yaml `toolCalling` 不识别**：2026.5.12 无此字段，删掉。
- **Canvas 401**：用 `start-canvas-proxy.sh`，不要手写 token 进 conf 再提交。

---

## 十一、部署时仍要自己改的硬编码

| 点 | 说明 |
|----|------|
| `$HOME/.openclaw-hr` | 课程默认；现行是 `$REPO/.openclaw-hr` |
| `/root/.openclaw-hr` | setup.sh 会改 |
| `/home/yhwz/openclaw-hr` | setup.sh **不会**改 |
| `hcm/start.sh` 里 miniconda 路径 | 本机 `/home/yhwz/miniconda3` |
| `cron/jobs.json` 脚本绝对路径 | 换目录必改 |
