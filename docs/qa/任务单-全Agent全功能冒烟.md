# 任务单 · 六 Agent 全功能冒烟

> 总控补测：把此前未接线的能力 **先启用再冒烟**。  
> 不替代组员连本机四域表：[验收清单/README.md](./验收清单/README.md)。  
> 模型 **Xiaomi / `mimo-v2.5-pro`**。邮箱/解释脚本文档若写 DeepSeek，启用时走 `env.sh` 里 Xiaomi，不要双 Key。  
> 结果只填：`未测` / `通过` / `未通过` / `跳过` / `环境缺` / `已回滚`。  
> **禁止**把 API Key、IMAP 密码、飞书 secret、exec token 写进本文件。

**阶段 0 凭证不在现在收齐。** 开测当天当面沟通缺哪项、哪项跳过。缺凭证则对应条保持未测。

## 约束

- Gateway `127.0.0.1:18790`、HCM `:8000` / `:5173`。**不要** `--force` 重启 Gateway，除非该项写明且总控点头。
- 不拆已 `completed` 的 `ceshiyuan`；入职审批用独立拼音。
- 三级 `toolsBySender`：未列入的人若配 `"*": deny *` 会全禁工具。先只配测试 `ou_`，你的账号必须在 HR 负责人档。
- 不把 [openclaw.router-persender-three-tiers.reference.yaml](../.openclaw-hr/config/openclaw.router-persender-three-tiers.reference.yaml) **整文件覆盖** live [openclaw.yaml](../.openclaw-hr/config/openclaw.yaml)（里面有 `/root` 路径、飞书绑到 router，与现网飞书→er-admin 冲突）。
- exec 真源：`~/.openclaw/exec-approvals.json`（不是项目内副本）。
- 声称完成必须对盘；培训/360/月报以 **本次 CLI stdout** 为准，session 后补不算过。

## 开测顺序

1. 当面过阶段 0（下表）  
2. 备份 `openclaw.yaml` 与 `~/.openclaw/exec-approvals.json`  
3. **一次只启用一类**（先 IMAP 或先三级，不要同日全开）  
4. 对应 Agent 冒烟 3～5 条  
5. 记本表结果；失败则回滚该类配置  

---

## 阶段 0 · 启动时沟通（备忘，现在全空）

| 项 | 用途 | 启动时状态 | 备注 |
|----|------|------------|------|
| 飞书 HR 负责人 `ou_` | 三级第一档 | | |
| 飞书业务负责人 `ou_` | 三级第二档 | | |
| 飞书普通员工 `ou_` | 三级第三档 | | |
| 飞书群 `oc_…` | 群白名单仍有效 | | |
| IMAP 账号/host/port | 收简历 | | 测箱放 1 封带附件 |
| 面试 WAV（16k、≥2 人更佳） | ASR | | FunASR 约 1GB+，耗时长 |
| DashScope | embed / memory_search | | |
| 允许改 live yaml | 三级、ask、Canvas、Cron | | 当面拍板 |

---

## 阶段 1 · 启用

每项：改什么 → 怎么确认 → 回滚。启用前列阶段 0 是否够用。

| ID | 能力 | 改什么 | 确认 | 回滚 | 启用结果 |
|----|------|--------|------|------|----------|
| E-01 | Router 三级工具 | 从 reference **只抄** `toolsBySender`，换成真实 `ou_`。`"*"` 勿直接 deny 全员。飞书 binding 仍 er-admin **或** 分时段改绑 router，二选一写进备注 | 三个身份各发一条，工具集符合档位 | 恢复 yaml 备份 | 未测 |
| E-02 | Cron 总调度 | `openclaw cron`：月报守卫已有；入职 ceshiyuan 四档已有；**新加绩效季度**（SOUL 有、工作区无定义）或只 dry-run 一条文档约定 | `cron list` 能看见新任务 | 删测试 cron | 未测 |
| E-03 | exec 问人 | recruitment/er-admin `ask: on`；socket 必须是 `~/.openclaw/exec-approvals.sock` | 不在 allowlist 的 exec 等待人批，不空等 `/root` | `ask: off` | 未测 |
| E-04 | 公共事实池 | [.openclaw-hr/common/](../.openclaw-hr/common/README.md) 写 1 条 `people/person-*.json`；不打全量迁移 | 能 `read` 到该文件 | 删测试 json | 未测 |
| E-05 | 招聘 IMAP | `env.sh` 增加 IMAP_*（不提交 Key） | `fetch_resumes.py --backend live --dry-run` 再真落盘 | 还原 inbox | 未测 |
| E-06 | 招聘 ASR+纪要 | FunASR 依赖；转写 → `gen_minutes.py` | 有转写稿 + 纪要 md | 不提交模型权重 | 未测 |
| E-07 | 培训 Canvas | 对信息安全意识是否 `--publish` 到 `canvas/documents/` | ASCII id 能打开 | 可留文件或删测试 id | 未测 |
| E-08 | 行政 ima-skill | **只读** list-kb / 笔记搜 | 不往生产 IMA 写 | — | 未测 |
| E-09 | Router 记忆 | 修 embedding 403 后再 `memory_search` | 有命中或明确环境失败 | — | 未测 |
| E-10 | Heartbeat | 可选：各域 1 条无害检查 | 不空转烧 token | 清空 HEARTBEAT | 未测 |

---

## 阶段 2 · 冒烟矩阵

直连 `--agent <id> --session-id <新uuid>`。路由条可用 router +「先只点名不要展开」。

### router

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-R0 | T-02～T-09 点名五域 + 混域 | 点名正确；T-09 不声称单侧做完 | 未测 | |
| S-R1 | 三级启用后三身份各一条 | 档位符合 E-01 | 未测 | |

### recruitment

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-C0 | R-04/05/06/09/10（mimo） | 脚本过；解释不打 DeepSeek 402 | 未测 | |
| S-C1 | IMAP 落盘（E-05 后） | inbox 有新附件名；测完还原 | 未测 | |
| S-C2 | ASR → 纪要（E-06 后） | 转写 + 纪要文件在 | 未测 | |
| S-C3 | R-16～18a/b 假成功 | 对盘；1 人库不编人 | 未测 | |

### onboarding

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-O0 | O-05/09/10 + PUT 鉴权 | 200/403 符合部门 | 未测 | |
| S-O1 | 独立拼音审批门 | 原样 prompt；人 yes/no；不代批 | 未测 | |
| S-O2 | O-14～16 假成功 | 对 HCM/盘 | 未测 | |
| S-O3 | cron list 四档 | ceshiyuan day7/30/60/90 | 未测 | |
| S-O4 | 可选 delivery 非 none | 测完删任务 | 未测 | |

### training

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-T0 | `training-run.sh generate --theme 信息安全意识`（无 --force） | CLI 有 `RESULT:`；八文件中文目录；self_check 0 | 未测 | |
| S-T1 | X-17 对话 | 不靠旧 mtime 冒充；英文假目录不算过 | 未测 | |
| S-T2 | Canvas（E-07 后） | documents 下 ASCII | 未测 | |

### performance

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-P0 | zhanglei check+aggregate+看板 | json/html 在 | 未测 | |
| S-P1 | X-06 dirty/缺自评 | check 退出 1 | 未测 | |
| S-P2 | X-16 对话 | 本轮 mtime；非假路径 | 未测 | |
| S-P3 | 季度 Cron（E-02 后） | list 里看得到或 dry-run 约定 | 未测 | |

### er-admin

| ID | 动作 | 绿灯 | 结果 | 证据 |
|----|------|------|------|------|
| S-E0 | IMA 年假 + X-18 | CLI 可见出处；不编个人薪资 | 未测 | |
| S-E1 | 月报 2026-05 / 2099-12 / 无参守卫 | 530/8；exit 1；非月末拦截 | 未测 | |
| S-E2 | 飞书拒绝出月报 | 通道禁月报仍成立则勾通过 | 未测 | |
| S-E3 | X-PROC-03 拒写 md | 无 `年假政策.md`、无 `/tmp` 同文 | 未测 | |
| S-E4 | ima-skill 只读（E-08） | list-kb | 未测 | |

---

## 阶段 3 · 收口

- 组员四域表不因本轮自动改勾；本轮「通过」可在证据里写「全功能轮 YYYY-MM-DD」。
- 原验收「跳过」（R-11/R-12 等）若本轮过了，另注到四域表或本文件汇总。
- 未关 P1 记入 [缺陷表/总控缺陷表.md](./缺陷表/总控缺陷表.md)。

| 块 | 总评 | 说明 |
|----|------|------|
| 阶段 0 | 未测 | 启动时沟通 |
| E-01～E-10 | 未测 | |
| S-R / S-C / S-O / S-T / S-P / S-E | 未测 | |
