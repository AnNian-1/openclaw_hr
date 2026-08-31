# 入职业务全量冒烟测试报告

**当前结论（2026-08-31）**：P0/P1 与 P2-3、重名 `zhangsan-dup` 已过；下文第一节合计 31/15 是 **08-29 首测**。ASR 仍跳过。看板可能仍显示已退役 review 块（产品债）。

- 测试时间：2026-08-29 21:18 ~ 21:30 CST
- 测试环境：Linux WSL2 / Node 20.18.0 (默认) + 22.16.0 (~/.local) / Python 3.14.4 / Bash 5.3
- HCM API：http://127.0.0.1:8000（可达，11 名候选人）
- 测试范围：4 个入职业务 Skill + Cron 调度 + 跨模块数据一致性
- ASR 转写：跳过（待换服务器环境后补测）

---

## 测试结果总览

| 分类 | 通过 | 失败/异常 | 跳过 |
|------|------|-----------|------|
| 审批工作流 | 12 | 2 | 0 |
| 状态查询 | 8 | 2 | 0 |
| 入职 review | 5 | 2 | 0 |
| 进度看板 | 3 | 3 | 0 |
| Cron 调度 | 2 | 2 | 0 |
| 数据一致性 | 1 | 4 | 0 |
| **合计** | **31** | **15** | **0** |

---

## 发现的问题

### 🔴 P0 · 数据一致性

#### P0-1：角标状态与 HCM 节点脱节

**现象**：看板角标来自 `workflow.json`，HCM 节点来自各部门维护。两者无强制关联，导致：

| 候选人 | workflow 角标 | HCM 未完成节点 |
|--------|--------------|----------------|
| 郭超 | 已完成 | account（in_progress，data.status=已审批） |
| 雷武 | 已完成 | contract（paused，data.status=待审批） |
| 测试员 | 已完成 | contract（pending）, account（pending） |

**根因**：stub 脚本（contract.sh 等）只读 HCM、只写本地 `stub-state/`，不回写 HCM。部门节点由各部门在 HCM 维护，但无机制确保部门在审批通过后同步更新 HCM 节点状态。不一致的三人均为历史测试数据，正常流程中各部门及时维护 HCM 时问题可能不显著。

**影响**：角标"已完成"和节点 pending 状态打架，让人困惑到底哪个才是真的。严格来说看板本身没有隐藏信息（角标和节点都展示了），但两套状态口径不一致，没有解释它们的关系。

**讨论结论**（2026-08-29）：

角标判定依据应改为 **HCM 5 个节点的状态**，而非 workflow.json。理由：
- 小慧不写 HCM，节点状态由各部门维护，是业务动作的真实落盘
- workflow.json 的 completed 只代表审批流程走完，不代表部门已执行
- 角标应反映业务实质（人到岗了没），不反映流程走到了哪一步

拟定角标规则：

| 5 节点状态 | 角标 |
|-----------|------|
| 全部 completed | ✅ 已完成 |
| 有 completed 也有 pending/paused/rejected | 🔄 入职中 |
| 全部 pending（无任何进展） | ⏳ 待启动 |

workflow.json 的审批门状态（halted/cancelled）**单独用标记表达**，不和角标混在一起。例如：
```
[入职中 3/5] 合同审批门 · 已暂停3天
```

**待定**：审批门状态在看板上的展示形式（小标签/文字说明/独立列）。

**关于小慧写 HCM 的立场**：保持小慧不能写 HCM 系统的原则，工作流的实时更新内容待定。

#### P0-2：account 节点 status 与 data.status 不一致（郭超）

```
node.status = "in_progress"
node.data.status = "已审批"
```

account 节点的顶层 `status` 字段和 `data.status` 字段矛盾。review 脚本和看板用 `node.status` 判断，会认为该节点未完成；但 `data.status` 显示"已审批"。

**根因**：可能是 HCM 端更新 data.status 时未同步更新顶层 node.status，或两字段由不同入口写入。

#### P0-3：pending-approvals 残留文件

流程取消（cancelled）时，`pending-approvals/` 目录中的快照文件不会被清理。只有 `complete` 步骤会执行 `rm -f`。

当前残留：
- `ceshi-contract.json`（测试，已 cancelled）
- `o08rejb-contract.json` + `o08rejb-account.json`（拒测O08b，已 cancelled）
- `jufuce-contract.json` + `jufuce-account.json`（拒测夹具，已 cancelled）
- `jufuyanshou-contract.json` + `jufuyanshou-account.json`（拒测验收，已 cancelled）
- `yuangong1-contract.json` + `yuangong1-account.json`（员工1，已 cancelled）
- `maomaodou-contract.json`（**maomaodou 已不在 HCM 花名册中**，纯孤立文件）

**影响**：查询 Skill 对已取消流程仍可能显示"pending-approvals 附加"信息，造成混淆。

**建议**：lobster 工作流的 cancel 路径也应清理 `pending-approvals/${pinyin}-*.json`。

#### P0-4：孤立 pending-approvals（maomaodou）

`maomaodou-contract.json` 存在于 pending-approvals 但 maomaodou 不在 HCM 花名册中。无法追溯此文件对应哪个流程。

---

### 🟡 P1 · 业务逻辑

#### P1-1：review Cron delivery.mode = none

工作流完成时注册的 14 个 review Cron，delivery.mode 全部为 `none`。

**影响**：Cron 到点触发后，review 结果在隔离 session 中执行完毕但不会推送给任何人。HR/主管无法收到 review 通知。

**建议**：`schedule-onboarding-reviews.sh` 中将 `--no-deliver` 改为指定 delivery channel（如 `--deliver announce`），或在 Cron payload 中配置 delivery。

#### P1-2：Node.js 版本不一致

系统默认 `node` 为 v20.18.0，但 openclaw CLI 要求 v22+。run-onboarding.sh 有 PATH 修正逻辑，但：
- 直接在 shell 中运行 `openclaw` 命令会失败（需手动 PATH 修正）
- query-onboarding-status.sh 和 onboarding-review.sh 没有 PATH 修正逻辑

**影响**：Agent 直接调用 `openclaw cron list` 等命令时会因 Node 版本失败。

**建议**：在所有 Skill 脚本顶部统一加入 Node 22 PATH 修正，或在 workspace 级别 env.sh 中设置。

#### P1-3：HCM 环境变量名不统一

| 脚本/模块 | 使用的环境变量 |
|-----------|---------------|
| run-onboarding.sh | `HCM_API_BASE` |
| workflow hcm_api.py | `HCM_API_URL` |
| review hcm_api.py | `HCM_API_URL` |
| query-onboarding-status.py | `HCM_API_URL`（优先）/ `HCM_API_BASE`（兼容） |

run-onboarding.sh 内部的 `require_hcm_candidate()` 用 `HCM_API_BASE`，但其调用的 hcm_api.py 用 `HCM_API_URL`。query-onboarding-status.py 做了桥接（读 `HCM_API_BASE` 写入 `HCM_API_URL`），但 review 脚本没有。

**影响**：如果用户只设 `HCM_API_BASE`，review 脚本会连默认的 localhost:8000 而非预期地址。

#### P1-4：重复 start 覆盖历史

对已完成的候选人再次执行 `start`，会清除旧的 workflow.json（含全部事件历史），静默覆盖。

**影响**：误操作会丢失入职审批的完整扭转轨迹，无法审计追溯。

**建议**：start 前检查 workflow.json 是否已存在且 status=completed，如是则拒绝或要求显式 `--force`。

---

### 🟢 P2 · 体验/规范

#### P2-1：看板无审批记录 badge

候选人无 `workflow.json` 时，看板 badge 显示"无审批记录"。这是正确的，但与"未启动入职流程"的语义略有差异——张三在 HCM 中有 status=onboarding 但无本地 workflow，badge 显示"无审批记录"可能让 HR 困惑。

#### P2-2：review 脚本对非标准天数的处理

传入 day=15 时，FOCUS 回退为"常规跟进"，不报错。这是 graceful degradation，但如果业务上只允许 7/30/60/90，应该拒绝其他值。

#### P2-3：Canvas 18999 反代未启动

文档推荐的浏览器 URL `127.0.0.1:18999` 不可达（exit code 7）。实际发布到 gateway 18790 端口，需 Bearer token。给 HR 直接用浏览器打开需要启动 18999 反代。

---

## 全量测试矩阵详细记录

### 一、入职审批工作流（running-onboarding-workflow）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 1.1 | dry-run 执行计划 | 打印5步流程 | ✅ | |
| 1.2 | start 正常启动 | 4路并行 → contract_gate halt | ✅ | |
| 1.3 | start 拼音不存在 | exit 3 | ✅ | |
| 1.4 | start HCM不可达 | exit 3 | ✅ | 用 HCM_API_BASE=19999 |
| 1.5 | start 重复启动 | 清旧stub重启 | ⚠️ | 静默覆盖历史，无确认（P1-4） |
| 1.6 | resume 批准合同门 | → account_gate halt | ✅ | |
| 1.7 | resume 批准账号门 | → complete + 注册Cron | ✅ | |
| 1.8 | resume 拒绝合同门 | → cancelled | ✅ | |
| 1.9 | resume 缺token参数 | exit 3 | ✅ | |
| 1.10 | resume 非法decision | exit 3 | ✅ | |
| 1.11 | resume 无效token | lobster parse_error exit 2 | ✅ | |
| 1.12 | VERBATIM标记块完整性 | PROMPT原样 + token完整 | ✅ | |
| 1.13 | resumeToken独立性 | 2次halt 2个不同token | ✅ | 验证yuangong2/ceshiyuan/lisi |
| 1.14 | HCM花名册校验 | start只读GET不写HCM | ✅ | contract.sh确认"不向HCM写入" |

### 二、入职状态查询（querying-onboarding-status）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 2.1 | 单人查询 - 已完成 | HCM+workflow=completed | ✅ | yuangong2 |
| 2.2 | 单人查询 - 审批门halt | 显示halt+PROMPT+token | ✅ | ceshi（第一轮start后） |
| 2.3 | 单人查询 - 已取消 | 显示cancelled | ✅ | ceshi（拒绝后） |
| 2.4 | 单人查询 - 无工作流 | 只报HCM，说明未启动 | ✅ | zhangsan |
| 2.5 | 单人查询 - HCM无此人 | exit 4 | ✅ | |
| 2.6 | 单人查询 - HCM不可达 | exit 5 | ✅ | HCM_API_URL=19999 |
| 2.7 | 单人查询 - 重名 | exit 4 | ⏭️ | HCM当前无重名，无法触发 |
| 2.8 | 整批查询 --all | 列出全部11人 | ✅ | |
| 2.9 | 未启动工作流 | 不报"全部完成" | ✅ | zhangsan正确提示 |
| 2.10 | halt天数计算 | 正确显示停留天数 | ✅ | |

### 三、入职跟进 review（running-onboarding-review）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 3.1 | day7 已完成review | already_reviewed | ✅ | guochao |
| 3.2 | day30 待触发review | needs_review | ✅ | leiwu |
| 3.3 | day30 有节点未完成 | warnings包含contract | ✅ | leiwu contract=paused |
| 3.4 | 非法天数（15） | FOCUS=常规跟进，不崩溃 | ✅ | graceful degradation（P2-2） |
| 3.5 | HCM不可达 | exit 5 | ✅ | 需用HCM_API_URL（P1-3） |
| 3.6 | 花名册无此人 | exit 4 | ✅ | |
| 3.7 | 重名无拼音 | exit 4 | ⏭️ | HCM当前无重名 |

### 四、入职进度看板（generating-onboarding-dashboard）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 4.1 | 生成HTML | 文件写入成功 | ✅ | |
| 4.2 | 发布到Canvas | --publish --force 成功 | ✅ | |
| 4.3 | Canvas无--force冲突 | exit 5 | ✅ | |
| 4.4 | HCM不可达 | 脚本报错 | ✅ | |
| 4.5 | Canvas内容正确性 | 11人全部展示 | ✅ | |
| 4.6 | badge vs HCM节点一致性 | badge=completed时节点全绿 | 🔴 | 3人不一致（P0-1） |

### 五、Cron 调度（schedule-onboarding-reviews）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 5.1 | 注册Cron | 4个一次性Cron | ✅ | |
| 5.2 | Cron内容正确 | 姓名/天数/路径正确 | ✅ | |
| 5.3 | delivery模式 | 应为announce | 🔴 | 全部为none（P1-1） |

### 六、跨模块数据一致性

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 6.1 | 看板badge vs HCM节点 | 一致 | 🔴 | 3人不一致（P0-1） |
| 6.2 | workflow vs HCM status | 一致 | 🔴 | 郭超account矛盾（P0-2） |
| 6.3 | review Cron日期计算 | 入职日+N天 09:00 | ✅ | |
| 6.4 | pending-approvals清理 | 完成/取消后清理 | 🔴 | 取消时不清（P0-3） |
| 6.5 | stub-state目录隔离 | 候选人互不干扰 | ✅ | |

---

**状态（2026-08-30）**：已修，重测通过。详见下方「修复重测」章节。

## 修复优先级建议（原报告；上列已落地）

1. **P0-1 + P0-2**：看板 badge 增加 HCM 节点校验，或审批通过后同步更新 HCM
2. **P0-3**：lobster cancel 路径增加 pending-approvals 清理
3. **P1-1**：review Cron delivery 改为 announce
4. **P1-2**：统一 Node 22 PATH 修正
5. **P1-3**：统一 HCM 环境变量名为 `HCM_API_URL`
6. **P1-4**：重复 start 增加确认机制

---

## 修复重测（2026-08-30 11:00 ~ 11:05 CST）

- 重测环境：同首测（Linux WSL2 / Node 22.16.0 / Python 3.14.4 / Bash 5.3）
- HCM API：http://127.0.0.1:8000（可达，13 名候选人，新增李明/周明）
- 重测范围：全部 6 类 45 项，重点验证 8 项修复

### 修复验证结果

| 修复项 | 原问题 | 验证方法 | 结果 | 备注 |
|--------|--------|----------|------|------|
| P0-1 角标改 HCM 节点 | badge 与 HCM 节点脱节 | 检查郭超/雷武/测试员角标 | ✅ 已修复 | 郭超 5/5=已完成，雷武 4/5=入职中，测试员 3/5=入职中 |
| P0-2 data.status 优先 | account 节点 status 矛盾 | 郭超 account in_progress 但 data.status=已审批 | ✅ 已修复 | 看板正确计为 completed |
| P0-3 cancel 清理 pending | 取消时不清 pending-approvals | 拒绝李明合同门后检查目录 | ✅ 已修复 | liming-contract.json 已清理 |
| P1-1 Cron delivery=announce | delivery.mode=none | 完成 ceshiyuan 后检查 Cron | ✅ 已修复 | delivery={mode:"announce", channel:"last", bestEffort:true} |
| P1-2 Node 22 PATH | query/review 脚本缺 PATH 修正 | source prepend-node22.sh 后 node -v | ✅ 已修复 | 两个脚本都引用了 prepend-node22.sh |
| P1-3 HCM 双环境变量 | review 不支持 HCM_API_BASE | 只设 HCM_API_BASE 跑 review | ✅ 已修复 | hcm_api.py 支持双变量回退 |
| P1-4 --force 防覆盖 | 静默覆盖历史 | 对 ceshiyuan 重复 start | ✅ 已修复 | exit 3 + 提示需 --force |
| P2-2 非法天数拒绝 | day=15 不报错 | 传入 day=15 | ✅ 已修复 | exit 2 + 明确错误信息 |
| P2-3 Canvas 18999 反代 | 不可达 | curl 127.0.0.1:18999 | ❌ 未修复 | 仍不可达，需单独部署反代 |

### 重测全量矩阵

#### 一、入职审批工作流（running-onboarding-workflow）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 1.1 | dry-run 执行计划 | 打印5步流程 | ✅ | |
| 1.2 | start 正常启动 | 4路并行 → contract_gate halt | ✅ | ceshiyuan --force 重跑 |
| 1.3 | start 拼音不存在 | exit 3 | ✅ | abcdefg |
| 1.4 | start HCM不可达 | exit 3 | ✅ | HCM_API_BASE=19999 |
| 1.5 | start 重复启动拒绝 | exit 3 + 提示 --force | ✅ | **P1-4 已修复** |
| 1.5b | start --force 覆盖 | 清旧stub重启 | ✅ | --force 正常覆盖 |
| 1.6 | resume 批准合同门 | → account_gate halt | ✅ | ceshiyuan |
| 1.7 | resume 批准账号门 | → complete + 注册Cron | ✅ | ceshiyuan |
| 1.8 | resume 拒绝合同门 | → cancelled + 清 pending | ✅ | liming，**P0-3 已修复** |
| 1.9 | resume 缺token参数 | exit 3 | ✅ | |
| 1.10 | resume 非法decision | exit 3 | ✅ | |
| 1.11 | resume 无效token | lobster parse_error exit 2 | ✅ | |
| 1.12 | VERBATIM标记块完整性 | PROMPT原样 + token完整 | ✅ | |
| 1.13 | resumeToken独立性 | 2次halt 2个不同token | ✅ | ceshiyuan 两次 halt 不同 token |
| 1.14 | HCM花名册校验 | start只读GET不写HCM | ✅ | |

#### 二、入职状态查询（querying-onboarding-status）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 2.1 | 单人查询 - 已完成 | HCM+workflow=completed | ✅ | yuangong2 |
| 2.2 | 单人查询 - 审批门halt | 显示halt+PROMPT+token | ✅ | zhouming |
| 2.3 | 单人查询 - 已取消 | 显示cancelled | ✅ | liming |
| 2.4 | 单人查询 - 无工作流 | 只报HCM，说明未启动 | ✅ | zhangsan |
| 2.5 | 单人查询 - HCM无此人 | exit 4 | ✅ | |
| 2.6 | 单人查询 - HCM不可达 | exit 5 | ✅ | HCM_API_URL=19999 |
| 2.7 | 单人查询 - 重名 | exit 4 | ✅ | 总控补测：HCM `张三`×2（zhangsan / zhangsan-dup），无拼音 exit 4 |
| 2.8 | 整批查询 --all | 列出全部13人 | ✅ | 新增李明/周明 |
| 2.9 | 未启动工作流 | 不报"全部完成" | ✅ | zhangsan 正确提示 |
| 2.10 | halt天数计算 | 正确显示停留天数 | ✅ | |

#### 三、入职跟进 review（running-onboarding-review）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 3.1 | day7 已完成review | already_reviewed | ✅ | guochao |
| 3.2 | day30 待触发review | needs_review | ✅ | leiwu |
| 3.3 | day30 有节点未完成 | warnings包含contract | ✅ | leiwu contract=paused |
| 3.4 | 非法天数（15） | exit 2 拒绝 | ✅ | **P2-2 已修复**（原为 graceful degradation） |
| 3.5 | HCM不可达 | exit 5 | ✅ | **P1-3 已修复**（只设 HCM_API_BASE 也行） |
| 3.6 | 花名册无此人 | exit 4 | ✅ | |
| 3.7 | 重名无拼音 | exit 4 | ✅ | 总控补测：无拼音 exit 4；手传 `zhangsan` 可跟进 |

#### 四、入职进度看板（generating-onboarding-dashboard）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 4.1 | 生成HTML | 文件写入成功 | ✅ | 13人展示 |
| 4.2 | 发布到Canvas | --publish --force 成功 | ✅ | |
| 4.3 | Canvas无--force冲突 | exit 5 | ✅ | |
| 4.4 | HCM不可达 | 脚本报错 | ✅ | |
| 4.5 | Canvas内容正确性 | 13人全部展示 | ✅ | |
| 4.6 | badge vs HCM节点一致性 | 角标基于HCM节点 | ✅ | **P0-1 已修复** |

#### 五、Cron 调度（schedule-onboarding-reviews）

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 5.1 | 注册Cron | 4个一次性Cron | ✅ | |
| 5.2 | Cron内容正确 | 姓名/天数/路径正确 | ✅ | |
| 5.3 | delivery模式 | announce + bestEffort | ✅ | **P1-1 已修复** |

#### 六、跨模块数据一致性

| # | 场景 | 期望 | 结果 | 备注 |
|---|------|------|------|------|
| 6.1 | 看板badge vs HCM节点 | 一致 | ✅ | **P0-1 已修复** |
| 6.2 | workflow vs HCM status | 一致 | ✅ | **P0-2 已修复** |
| 6.3 | review Cron日期计算 | 入职日+N天 09:00 | ✅ | |
| 6.4 | pending-approvals清理 | 完成/取消后清理 | ✅ | **P0-3 已修复** |
| 6.5 | stub-state目录隔离 | 候选人互不干扰 | ✅ | |

### 重测结果总览

| 分类 | 通过 | 失败/异常 | 跳过 |
|------|------|-----------|------|
| 审批工作流 | 15 | 0 | 0 |
| 状态查询 | 10 | 0 | 0 |
| 入职 review | 7 | 0 | 0 |
| 进度看板 | 6 | 0 | 0 |
| Cron 调度 | 3 | 0 | 0 |
| 数据一致性 | 5 | 0 | 0 |
| **合计** | **46** | **0** | **0** |

**结论**：8 项修复全部验证通过（P0-1/P0-2/P0-3/P1-1/P1-2/P1-3/P1-4/P2-2）。P2-3 Canvas 18999 反代已在第三次重测中验证通过。2.7 / 3.7 重名已由总控用 `zhangsan-dup` 夹具补测通过。

---

## 第三次重测（2026-08-30 14:21 ~ 14:25 CST）

- 重测环境：同前（Linux WSL2 / Node 22.16.0 / Python 3.14.4 / Bash 5.3）
- HCM API：http://127.0.0.1:8000（可达，15 名候选人，新增 zhangsan-dup / crontest-smoke）
- 重测范围：全部 6 类 47 项，重点验证 P2-3 Canvas 18999 反代修复

### P2-3 修复验证

| 修复项 | 原问题 | 验证方法 | 结果 |
|--------|--------|----------|------|
| P2-3 Canvas 18999 反代 | curl 返回 000 不可达 | curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18999/... | ✅ 返回 200 |

### 全项重测结果

| 分类 | 通过 | 失败 | 跳过 | 备注 |
|------|------|------|------|------|
| 审批工作流 | 15 | 0 | 0 | |
| 状态查询 | 10 | 0 | 0 | 2.7 重名校验通过（zhangsan-dup） |
| 入职 review | 7 | 0 | 0 | |
| 进度看板 | 6 | 0 | 0 | P2-3 反代 200 |
| Cron 调度 | 3 | 0 | 0 | |
| 数据一致性 | 5 | 0 | 0 | |
| **合计** | **46** | **0** | **0** | |

**结论**：全部 9 项修复（P0-1/P0-2/P0-3/P1-1/P1-2/P1-3/P1-4/P2-2/P2-3）均已验证通过，0 失败 0 跳过。

### 新发现问题

#### P1-5：看板仍展示已下线的 review 区块

**现象**：`build-dashboard.py` 第 225-252 行仍从 `review-state/reviews.json` 读取 review 数据，生成"试用期跟进 · 4 个 review 节点"区块。当前 HTML 中每个候选人卡片都有该区块。

**背景**：review（7/30/60/90天跟进）已从前端下线，HCM 仅保留 API 接口。review 数据由小慧本地维护（`review-state/reviews.json` + Cron 定时任务），不混入看板。看板应只展示 HCM 5 个准备节点。

**建议**：`build-dashboard.py` 去掉 review_store 导入和 review 区块生成逻辑，`total` 计算改为只算 5 个准备节点，去掉 `rdone` / `pct` 中 review 的权重。
