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

## 部门视图

看板采用**左侧部门栏 + 右侧候选人列表**布局：

- 左侧固定 5 个部门父栏：HR / IT / 行政 / 培训部 / 用人部门
- 点击某部门后，右侧列出全部候选人，**每张卡只展示该部门负责的入职节点**，且可编辑
- 卡片右上角薪资下方为 **5 个圆点**（合同 / IT / 行政 / 培训 / Buddy），颜色对应该节点实时状态；当前部门那颗带描边。悬停显示节点名与状态。流程已取消时另标「已取消」
- 侧栏角标显示该部门节点仍为「未开始 / 进行中」的人数
- HR 栏额外可编辑花名册（姓名 / 岗位 / 薪资）
- **试用期 7/30/60/90 天跟进不在本看板维护**；真相源为入职工作区 `review-state/reviews.json`（入职小慧维护）。HCM 后端 `reviews` 表/API 为遗留字段，待本地表稳定后再删。

| 部门 | 可编辑节点 |
|------|-----------|
| HR | 合同签署 (contract) |
| IT | IT账号 (account) |
| 行政 | 行政设备 (device) |
| 培训部 | 入职培训 (training) |
| 用人部门 | Buddy匹配 (buddy) |

写入节点时前端会带 `X-Department-Role` 请求头；后端按部门校验，跨部门修改返回 403。小慧（Agent）仍只 `GET` 花名册，不向 HCM 写入。
