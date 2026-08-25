# HCM 入职管理系统

模拟 HCM 数据源系统 — 各部门通过前端填写入职准备数据，小慧通过 GET API 只读查询数据。

## 快速启动

```bash
# 1. 初始化数据库 + 导入现有数据
cd backend && python seed.py

# 2. 一键启动
cd .. && bash start.sh
```

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
| GET | `/api/candidates` | 候选人列表 |
| GET | `/api/candidates/{id}` | 候选人详情 |
| POST | `/api/candidates` | 新增候选人 |
| PUT | `/api/candidates/{id}/prep/{node}` | 更新节点状态 |
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
