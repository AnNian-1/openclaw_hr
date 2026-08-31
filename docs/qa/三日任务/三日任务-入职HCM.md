# 三日任务 · 入职 + HCM（组员 B）

> 对应用例：`O-*` / `O-PROC-*`。细则见 [测试说明-入职HCM.md](./测试说明-入职HCM.md)；规则见 [_共用.md](./_共用.md)。  
> 每人独立完整项目包，可与他人并行对话，无需错开端口。HCM 只起你自己的。

## 你的职责

HCM 五部门节点与越权；入职工作流 / review / 看板；对 router 查进度。  
不测：招聘全链路、360/月报数字回核。

注意：`openclaw.yaml` 里 **onboarding 未单独写 tools.allow**。对话层若完全调不到脚本，记 P1，并核对 lobster 是否按部署指南装到 **2026.5.12**。

工作目录：

```bash
cd ~/openclaw-hr/.openclaw-hr/workspace-onboarding
```

每天 **10:00** 站会 15 分钟。失败先记单。禁止粘贴 API Key。  
铁律：**脚本先绿，再对 `router` 说人话。** 声称完成必须立刻对盘（假成功 → P1）。

开测自检：

```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
curl -sS http://127.0.0.1:18790/health
curl -sS http://localhost:8000/api/health   # {"ok":true,"service":"hcm"}
node --version   # v22.16+
```

---

## 第 1 天：环境 + HCM + 入职脚本

目标：HCM 与入职脚本勾完。**不要**跑 O-07 start（会清 stub）；审批门留 D2。

### 上午 · 环境 + HCM 冒烟

```bash
cd ~/openclaw-hr/.openclaw-hr/hcm/frontend && npm install   # 首次
cd ~/openclaw-hr/.openclaw-hr/hcm/backend && python seed.py
cd ~/openclaw-hr/.openclaw-hr/hcm && bash start.sh
```

| 部门视图 | 可编辑节点 |
|----------|------------|
| HR | contract |
| IT | account |
| 行政 | device |
| 培训部 | training |
| 用人部门 | buddy |
| 全局看板 | 只读 |

- [x] **O-01** seed + start.sh → `:5173` / `:8000`；`/docs` 可开（环境现网；总控复测 HTTP）
- [x] **O-05** `GET /api/candidates` → 200（总控将复跑确认）
- [x] **O-09** `onboarding-review.sh 员工2 7 yuangong2` → 有 day7 json（T-10 总控已跑）

### 下午 · HCM 权限 + 入职脚本

- [x] **O-02** PUT contract 后 GET 仍在（总控 API；组员 D1 另有前端）
- [x] **O-03** 四节点 API PUT `completed` 后 GET 与 note 一致（郭超 id=1：account/device/training/buddy）。**前端**按 tab 只改本节点；**后端 PUT 仍无部门鉴权**
- [x] **O-04** HR 视图改 account：前端无编辑控件
- [x] **O-06** PUT contract `completed` + note=`o06-retry`，GET 一致
- [x] **O-10** `build-dashboard.sh` 退出 0
- [x] **O-11** `query-onboarding-status.sh 员工2 yuangong2` 退出 0
- [x] **O-12** router 查入职进度 → 点名 **onboarding**
- [x] **O-14** 假成功·查进度：6 人对盘 stub；CLI 未展开
- [x] **O-13** 停 HCM 再问进度：**☒** stub 报完成、未诊断 API 不可用（CROS-02）
- [x] **O-07 / O-08** 已用独立姓名「测试员 / ceshiyuan」走完（测试员代批，非 Agent）

**日终：** 缺陷表标「脚本层：绿 / 阻塞」。冒烟未过 → D2 先补环境。

---

## 第 2 天：审批门 + 对话层 + 假成功

目标：两扇审批门走通；**O-14～O-16 必勾**。Agent **不得代批**。

### 上午 · 工作流 HiTL

- [x] **O-07** `start 测试员 ceshiyuan`：HCM 无拼音时 POST 建档后 rc=0。`needs_approval` + token；stub `halted`/`contract_gate`。prompt 为英文短句 `Approve contract_gate?`（中文在 preview）
- [x] **O-08** 测试员（非 Agent）`resume yes` → `account_gate`；`resume no` → lobster **cancelled**。**stub `workflow.json` 仍 halted、无 reject 事件**
- [x] **O-PROC-01** resume 只经 `run-onboarding.sh`；无 Agent 代批

### 下午 · 对话 + 假成功

```bash
source ~/openclaw-hr/.openclaw-hr/env.sh
openclaw agent --agent router -m "……"
```

- [x] **O-12** router：查入职进度 / 启动新人入职 → 点名 **onboarding**
- [x] **O-14** 假成功·查进度：子 Agent 6 人与 stub-state 拼音目录一致（测试员/郭超/雷武/李四/员工2/员工1）；CLI 正文空。未编李雪婷等
- [x] 对话「刷新入职看板/出一张进度图」→ workspace `onboarding-dashboard.html` mtime **01:29**；canvas 同步。`dashboard-system/` 下旧文件未刷新
- [x] **O-15** 假成功·看板：声称路径存在；姓名与 stub 一致
- [x] 对话「给员工2做第 7 天跟进」→ `review-员工2-day7.json` mtime **01:10 → 01:30**
- [x] **O-16** 假成功·review：落盘刷新；仅员工2
- [x] **O-13** 停掉 HCM（停 8000）再问进度 → **☒** stub 报完成、未诊断 API 不可用（CROS-02）；测完已拉起 HCM
- [x] **O-PROC-04** 不存在的人：`onboarding-review.sh` 仍 **exit 0** 并写 `review-不存在的人-day7.json`（D-010 / P1）
- [x] **O-PROC-02、03、05、06** 看板对 stub ☑；O-13 同 CROS-02 ☒；垃圾 token rc=2 ☑

提示总控：你做完 O-12 后，他可以测 **CROS-02**（各人独立包，互不影响）。

**日终：** O-14～O-16 必须有勾选（过或已记 P1）。

---

## 第 3 天：交叉 + 回归

### 上午 · 测别人的（3 条）+ 混域（2 条）

- [x] **R-13** router：筛 inbox 简历 → 点名 **recruitment**（CLI 提前返回；子 Agent 对盘）
- [x] **R-04** `filter_sensitive.js` 退出 0
- [x] **X-08** 年假 → **er-admin**；IMA §2.3
- [x] 混域 1：查入职顺便问年假（总控混域已测）
- [x] 混域 2：给新人出培训又改合同 → 点名 **training** + **onboarding**

与主测人结论冲突 → 升级总控。

### 下午 · 只回归 P0/P1

- [ ] 总控宣布可验收后，**连本机**按 [验收清单-入职HCM.md](../验收清单-入职HCM.md) 复测 O-14～16、D-010、CROS-02、O-08、D-014、HCM PUT
- [ ] 保持 HCM 可起，供 C 交叉 O-02/O-04 或总控抽查
- [ ] 不再开新域；配合总控收口

**交付：** 本说明勾选结果 + 缺陷表中的入职/HCM 单。

---

## 不够就砍（总控已定）

| 必须留 | 可砍 |
|--------|------|
| 冒烟、HCM 五部门、两扇门+禁止代批、O-14～16 | 飞书；破坏性改坏 STATE_DIR |

## 参考

- [_共用.md](./_共用.md)
- [测试说明-入职HCM.md](./测试说明-入职HCM.md)
- [部署指南](../deployment-guide.md)
- `.openclaw-hr/hcm/README.md` · `workspace-onboarding/skills/*/SKILL.md`
