# 主节点复跑验证记录

**验证窗口**：2026-09-03 约 19:48–21:51 Asia/Shanghai  
**对照基线快照**：`20260903T114546Z`（`/opt/openclaw-hr/.openclaw-hr/ops/memory-snapshots/20260903T114546Z`）  
**终态扫描**：`replay-watch.py --write` @ 2026-09-03 21:51:20 +0800

## 结论

- **记忆层合格**：10 份域日记，**闸词 0 命中**；无 `MEMORY.md`；无 `memory/dreaming/` 报告。
- **四服务正常**：hcm-backend / hcm-frontend / gateway / canvas 均为 HTTP 200。
- **session-memory 在写**：符合预期；测试员会话未污染已批准长期记忆。
- **做梦**：验证期间 cron 原为 23:00；验证结束后 operator 先后改为 21:55、再改为 **22:00** 以便观测第一轮 dream。

## 计数（终态）

| 项 | 值 |
|----|-----|
| 日记 | 10 |
| MEMORY.md | 0 |
| dreaming 报告 | 0 |
| sqlite 已索引文件 | 1（onboarding 旧 9/1 日记） |
| session keys | 25 |
| jsonl | 25 |

## 域覆盖（组员 SSH 复跑）

| 域 | 要点 |
|----|------|
| er-admin | 政策问答 8 份日记，口径干净（年假、社保、工资转人工、绩效 C 升级、差旅三档、拒月报、拒招前端）；飞书 HR 测试号问三级权限 → 知识库 0 命中转人工 |
| onboarding | 员工1 看板、--force 重开审批、两门批准、试用期 cron、第 7 天手动催办；**旧日记仍写「审批已取消」** |
| recruitment | fetch-mail、面试者1 评分 D、人才库 8 人、相似检索；面试 ASR/纪要完成；**会话含闸词真人名/音频文件名 zhanglei，日记未落** |
| training | 项目测试完整物料 generate 完成 |
| performance | 员工1 360（领导1/同事/下属/自评夹具），已有 aggregated 报告 |
| router | Rokid 插件、webchat；曾自重启；一次自行解释飞书权限（勿进 MEMORY.md） |
| gateway | 20:14 SIGTERM 后 `hr-service.sh start` 恢复；组员勿 `openclaw gateway stop` |

## 23:00 合并前勿自动 promote 的内容

- 真名 PDF / 云南大学 / `xingqiao-tech` / `zhanglei`·张磊
- 员工1 矛盾口径（cancelled vs 五节点齐 + cron）
- 面试者1 当花名册真人；HEARTBEAT_OK 若出现在日记

## 做梦观测（改点后）

- yaml `frequency`: `0 22 * * *`，`timezone`: `Asia/Shanghai`（2026-09-03 验证后 operator 定为 22:00）
- 报告出现后：`memory-snapshot.sh` → `dream-report-gate.sh` → 人审 → 手工合并 `MEMORY.md`
- **禁止** `memory promote --apply`
- 22:00 首轮 dreaming：recruitment light 报告闸词已手工脱敏（详见 `ops/memory-open-items.md`）；`江政宾` / `云南大学` soft 残留改日处理
