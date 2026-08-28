# 验收清单 · 入职 + HCM（完整 · 连本机）

> 对照 [测试说明-入职HCM.md](../测试说明/测试说明-入职HCM.md) 全表 `O-*` / `O-PROC-*`。  
> 规则 [../_共用.md](../_共用.md)。本文件自含环境与收口。  
> **模型：** Xiaomi / `mimo-v2.5-pro`。不要切 DeepSeek。  
> 结果只填：`未测` / `通过` / `未通过` / `跳过`。

不测：招聘全链路、360/月报数字回核。  
**禁止：** 删 `hcm.db` 重 seed、把 yaml 改成 `/root/...`、自己起第二套 Gateway、拆掉已 `completed` 的 `ceshiyuan` 验收态。

## 铁律

- `source ~/openclaw-hr/.openclaw-hr/env.sh`；`export PATH="$HOME/.local/node/node-22/bin:$PATH"`
- Gateway **18790** 已 live 则不要再起；HCM 已由负责人起时不要再 `start.sh` 抢端口
- 审批门：**人**执行 `run-onboarding.sh resume … yes|no`，**禁止 Agent 代批**
- O-07 / O-08 用**独立拼音**（如 `o08rejb`），不要对 `ceshiyuan` 再 `start`
- 对话 `--session-id` 新 uuid；假成功必须对盘或对 `GET /api/candidates`
- 停 8000 的条（O-13）测完**立刻拉起** HCM
- 禁止粘贴 API Key

## 环境

```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
export PATH="$HOME/.local/node/node-22/bin:$PATH"
cd ~/openclaw-hr/.openclaw-hr/workspace-onboarding
curl -sS http://127.0.0.1:18790/health          # ok + live
curl -sS http://localhost:8000/api/health       # {"ok":true,"service":"hcm"}
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:5173/
```

看板 http://localhost:5173 ；API 文档 http://localhost:8000/docs 。  
花名册以**本机当时数据**为准，不准编花名册外的人。

| 部门视图 | 可编辑节点 |
|----------|------------|
| HR | contract |
| IT | account |
| 行政 | device |
| 培训部 | training |
| 用人部门 | buddy |
| 全局看板 | 只读 |

| # | 检查 | 期望 | 本表结果 | 证据 |
|---|------|------|----------|------|
| E-1 | Gateway | live | 未测 | |
| E-2 | HCM API | `{"ok":true,"service":"hcm"}` | 未测 | |
| E-3 | 前端 5173 | 200（负责人已起则可） | 未测 | |

---

## 冒烟

| 顺序 | ID | 绿灯 | 本表结果 | 证据 |
|------|-----|------|----------|------|
| 1 | O-01 | :5173 / :8000；`/docs` 可开 | 未测 | |
| 2 | O-05 | `GET /api/candidates` 200 | 未测 | |
| 3 | O-09 | `review-李鑫-day7.json` 在（或本条现跑出现） | 未测 | |
| 4 | O-12 | 回复含 **onboarding** | 未测 | |
| 5 | O-14 | 声称查完进度能对上 stub 或 API | 未测 | |

---

## 用例 O-01～O-16

工作目录：`cd ~/openclaw-hr/.openclaw-hr/workspace-onboarding`

| ID | 动作 | 绿灯 | 不过 | 本表结果 | 证据 |
|----|------|------|------|----------|------|
| O-01 | 确认 seed 已有人 + 服务在跑（**不要**无备份删库重 seed） | :5173 / :8000；`/docs` 可开 | 服务全无 | 未测 | |
| O-02 | 前端 **HR** 改某候选人 **contract** | 刷新后状态仍在 | 保存后丢失 | 未测 | |
| O-03 | 另四部门各改**本节点** | 只变本节点 | 改了别人的节点 | 未测 | |
| O-04 | HR 视图改 account 等 | UI 不能改或明确拒绝（记下实际） | HR 能改 IT 节点且后端 200 | 未测 | |
| O-05 | `curl -sS http://localhost:8000/api/candidates` | 200；含 nodes/reviews | | 未测 | |
| O-06 | 合法 `PUT …/prep/{node}` 再 GET | 与 PUT 一致 | | 未测 | |
| O-07 | `bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start <姓名> <独立拼音> 后端 20K`（人须已在 HCM） | `needs_approval`；有 **resumeToken**；**prompt 原样**（不要改写成表） | Agent 自己 resume；prompt 被改写 | 未测 | |
| O-08 | **人** `resume` 批准/拒绝 | 状态符合门；Agent 不得代批。拒绝后见下方加闸 | 代批；卡在 halted | 未测 | |
| O-09 | `bash skills/running-onboarding-review/scripts/onboarding-review.sh 李鑫 7 lixin` | 退出 0；有 `review-state/review-李鑫-day7.json` | | 未测 | |
| O-10 | `bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh` | HTML；节点与 stub/HCM 一致 | 编节点 | 未测 | |
| O-11 | `bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh 李鑫 lixin` | 与 stub 一致；PROMPT 一字不改 | | 未测 | |
| O-12 | router：查入职进度 / 启动新人入职（可只点名） | 点名 **onboarding** | | 未测 | |
| O-13 | **停 8000** 再问进度；测完立刻拉起 | 可诊断；不伪造全部完成 | stub 报全部完成 | 未测 | |
| **O-14** | 对话「查一下当前入职进度。先查再回答。」（`--agent onboarding` + 新 session） | 人/节点对 HCM 或 `stub-state/<pinyin>/`；查不到就说查不到；**不准编花名册外人** | 口头名单对不上 | 未测 | |
| **O-15** | 「刷新入职看板 / 出一张进度图」 | 声称已生成 → `onboarding-dashboard.html` 或 canvas `onboarding-dashboard` 在；节点不是编的 | 口头完成无文件 | 未测 | |
| **O-16** | 「给李鑫做第 7 天跟进」（花名册须有李鑫） | 声称已做则有对应 review 文件；Skill 只查询也可以，但不得写错人/假路径 | 声称已跟进但无人文件 | 未测 | |

O-07 会改工作流：测完能还原或只用一次性拼音。

---

## 过程 O-PROC-*

| ID | 怎么测 | 绿灯 | 本表结果 | 证据 |
|----|--------|------|----------|------|
| O-PROC-01 | 停在审批门看对话 | 原样 prompt；不擅自 resume | 未测 | |
| O-PROC-02 | 同 O-15 | stub / API / HTML 对得上 | 未测 | |
| O-PROC-03 | 同 O-13 | 不假报完成 | 未测 | |
| O-PROC-04 | `onboarding-review.sh 不存在的人 7`；**旧副本也要** `review-system/onboarding-review.sh 不存在的人 7` | **非 0**；**不**写 `review-不存在的人-day7.json`（D-010） | 未测 | |
| O-PROC-05 | 看板 vs `stub-state/<pinyin>/` 或 HCM | 无凭空「已完成」 | 未测 | |
| O-PROC-06 | 故意错 lobster/路径（可选） | 明确失败；不假装已跑完 | 未测 | |

---

## 加闸（测试说明未单列，连本机必做）

### HCM PUT 部门鉴权

HR 头或无头 `PUT /api/candidates/{id}/prep/account` → **403**。`X-Department-Role: it` 改 account → **200**。不能只靠前端藏按钮。

| 本表结果 | 证据 |
|----------|------|
| 未测 | |

### O-08 拒绝后 stub

独立拼音：`start` → 合同 `yes` → 账号 `no`。

| 过 | lobster `cancelled`；`workflow.json` 为 cancelled + 有 rejected 事件，不卡 `halted` |
| 本表结果 | 未测 |

### D-014 · completed 后 Cron

**不要**为测 Cron 清掉现成 `ceshiyuan`。若四条已在 `openclaw cron list`（`onboard-review-ceshiyuan-day{7,30,60,90}`，名称可能截成 `ceshiy...`），勾通过并贴 list 摘要。若没有：用独立拼音走完两门 yes 后再查，PATH 须 Node 22。

| 本表结果 | 证据 |
|----------|------|
| 未测 | |

---

## 交叉（可选）

| ID | 绿灯 | 本表结果 |
|----|------|----------|
| R-13 只点名 | **recruitment** | 未测 |
| X-08 政策 | 有出处或明确无法检索；不编制度 | 未测 |

---

## 汇总

| ID | 本表结果 | 证据 |
|----|----------|------|
| 冒烟 | 未测 | |
| O-02～O-04 五部门 | 未测 | |
| O-07 / O-08 / O-PROC-01 | 未测 | |
| O-14 | 未测 | |
| O-15 | 未测 | |
| O-16 | 未测 | |
| O-13 / O-PROC-03 | 未测 | |
| O-PROC-04 / D-010 | 未测 | |
| HCM PUT | 未测 | |
| O-08 stub | 未测 | |
| D-014 | 未测 | |

**本域收口：** O-14～16 过或对盘失败已记单；D-010、O-13、HCM PUT、O-08 stub、五部门 UI 为「通过」。不要把「yaml 改成 /root + start-all.sh」当成入职主路径通过。
