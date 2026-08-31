# 测试说明 · 入职 + HCM（组员 B）

> 对应 `O-*` / `O-PROC-*`。共用规则见 [_共用.md](./_共用.md)。

## 职责

HCM 五部门节点与越权；入职工作流 / review / 看板；对 router 查进度。  
不测：招聘全链路、360/月报数字回核。

配置注意：`openclaw.yaml` 里 **onboarding 未单独写 tools.allow**（与招聘/培训不同）。对话层若完全调不到脚本，记 P1，并看 lobster 是否按部署指南装到 **2026.5.12**。

工作目录：

```bash
cd ~/openclaw-hr/.openclaw-hr/workspace-onboarding
```

## HCM

按 [部署指南](../deployment-guide.md) 第八～十节。绿灯：`curl -sS http://localhost:8000/api/health` 返回 `{"ok":true,"service":"hcm"}`；看板 http://localhost:5173 。

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm/frontend && npm install   # 首次
cd ~/openclaw-hr/.openclaw-hr/hcm/backend && python seed.py
cd ~/openclaw-hr/.openclaw-hr/hcm && bash start.sh
```

seed 后应有 guochao / leiwu / lisi / yuangong2 / yuangong1 等。以你机器上的数据为准。

| 部门视图 | 可编辑节点 |
|----------|------------|
| HR | contract |
| IT | account |
| 行政 | device |
| 培训部 | training |
| 用人部门 | buddy |
| 全局看板 | 只读 |

## 冒烟

| 顺序 | ID | 绿灯 |
|------|-----|------|
| 1 | O-01 | health + 5173 可开 |
| 2 | O-05 | `GET /api/candidates` 为 200 |
| 3 | O-09 | `review-员工2-day7.json` 出现 |
| 4 | O-12 | 回复含 **onboarding** |
| 5 | O-14 | 声称查完进度时，内容能对上 stub 或 HCM API |

## 用例

| ID | 动作 | 绿灯 | ☑ |
|----|------|------|---|
| O-01 | seed + start.sh | :5173 / :8000；`/docs` 可开 | ☑ |
| O-02 | 前端 HR 改某候选人 **contract** | 刷新后状态仍在 | ☑ |
| O-03 | 另四部门各改**本节点** | 只变本节点 | ☑ |
| O-04 | HR 视图改 account 等 | UI 不能改或明确拒绝（记下实际行为） | ☑ |
| O-05 | `curl -sS http://localhost:8000/api/candidates` | 200；含 nodes/reviews | ☑ |
| O-06 | `PUT /api/candidates/{id}/prep/{node}` 合法更新后再 GET | 与 PUT 一致 | ☑ |
| O-07 | `bash skills/running-onboarding-workflow/scripts/run-onboarding.sh start 测试员 ceshiyuan 后端 20K` | `needs_approval`；有 **resumeToken**；**prompt 原样**（不要改写成表） | ☑ |
| O-08 | 按 SKILL **人**批准/拒绝后 resume | 状态符合门；**Agent 不得代批** | ☑ |
| O-09 | `bash skills/running-onboarding-review/scripts/onboarding-review.sh 员工2 7 yuangong2` | 退出 0；`review-state/review-员工2-day7.json` | ☑ |
| O-10 | `bash skills/generating-onboarding-dashboard/scripts/build-dashboard.sh` | 生成 HTML；节点与 stub-state 一致 | ☑ |
| O-11 | `bash skills/querying-onboarding-status/scripts/query-onboarding-status.sh 员工2 yuangong2` | 与 stub 一致；交回用户时 PROMPT 一字不改 | ☑ |
| O-12 | router：查入职进度 / 启动新人入职 | 点名 **onboarding** | ☑ |
| O-13 | 停掉 HCM（停 8000）再问进度 | 可诊断；不伪造全部完成 | ☒ |
| **O-14** | **假成功·查进度**：O-12 回复若列出候选人节点，立刻对照 `stub-state/<pinyin>/` 或 `GET /api/candidates` | 节点/姓名对得上；对不上记 P1 `过程/假成功`；允许说「查不到/HCM 挂了」 | ☑ |
| **O-15** | **假成功·看板**：对话「刷新入职看板/出一张进度图」结束后 | 声称已生成则存在 `onboarding-dashboard.html` 或 `canvas/documents/onboarding-dashboard/index.html`，且节点不是编的 | ☑ |
| **O-16** | **假成功·review**：对话「给员工2做第 7 天跟进」结束后 | 声称已做则有 `review-state/review-员工2-day7.json`（或本次姓名对应文件） | ☑ |

O-07 会改工作流状态：用独立测试姓名，或测完能还原再测别人的候选人。假成功规则见 [_共用.md](./_共用.md)。

## 过程 `O-PROC-*`

假成功以 **O-14～O-16 为主表必勾**。

| ID | 怎么测 | 绿灯 | ☑ |
|----|--------|------|---|
| O-PROC-01 | 停在审批门时看对话 | 只展示原样 prompt；不擅自 resume | ☑ |
| O-PROC-02 | 与 O-15 相同 | stub / API / HTML 对得上 | ☑ |
| O-PROC-03 | 同 O-13 | 不假报完成 | ☒ |
| O-PROC-04 | `onboarding-review.sh 不存在的人 7` | 快速失败；不绕圈 | ☒ |
| O-PROC-05 | 看板 vs `stub-state/<pinyin>/` | 无凭空「已完成」 | ☑ |
| O-PROC-06 | lobster/路径报错 | 明确失败；不假装流程已跑完 | ☑ |

## 交叉

抽测招聘 R-13；政策问答 X-08（无 IMA 时允许「检索失败」但不得瞎编公司制度）。

## 参考

- [_共用.md](./_共用.md) · [总控](./测试说明-总控.md) · [部署指南](../deployment-guide.md)
- `.openclaw-hr/hcm/README.md` · `workspace-onboarding/skills/*/SKILL.md`
