# HCM 入职管理系统

模拟 HCM 数据源系统 — 各部门通过前端填写入职准备数据，小慧通过 GET API **只读**查询数据，**不向 HCM 写入**。

## 快速启动

```bash
# 1. 初始化数据库 + 导入现有数据
cd backend && python seed.py
# seed 可从 workspace-onboarding/stub-state 灌演示候选人；运行期新建人请走下方 SOP

# 2. 一键启动
cd .. && bash start.sh
```

## SOP · 新人入职（HCM 花名册先行）

小慧启动入职工作流前，花名册里必须已有该人（按 **拼音** 匹配）：

1. **先在 HCM 建档**：看板新增，或 `POST http://localhost:8000/api/candidates`（body 含 `name` / `pinyin` / `role` / `salary`）。
2. **再让小慧 start**：`run-onboarding.sh start <姓名> <拼音> <岗位> <薪资>`。  
   脚本只 GET 花名册；拼音不存在或服务挂了会直接失败，不会在 HCM 里悄悄建人。
3. **五部门节点**仍只在 HCM 前端/API 由各部门更新；小慧工作流写的是本机 `stub-state/`。

这样保证：HCM 看板能看见的人 = 已经人工建过档；小慧不碰 HCM 写入。

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端看板 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |

## 架构

```
各部门 → Vue前端 → FastAPI后端 → SQLite
                    ↓ GET 只读
                小慧（Agent）
                    ↓ WebSocket
                看板页面
```

## API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/candidates` | 候选人列表（小慧只读校验用） |
| GET | `/api/candidates/{id}` | 候选人详情 |
| POST | `/api/candidates` | 新增候选人（**人 / 看板**，不是小慧） |
| PUT | `/api/candidates/{id}/prep/{node}` | 更新节点状态（各部门） |
| GET | `/api/candidates/{id}/reviews` | review 列表 |
| PUT | `/api/candidates/{id}/reviews/{type}` | 更新 review |

## 部门视图

| 部门 | 可编辑节点 |
|------|-----------|
| HR | 合同签署 (contract) |
| IT | IT账号 (account) |
| 行政 | 行政设备 (device) |
| 培训部 | 入职培训 (training) |
| 用人部门 | Buddy匹配 (buddy) |
