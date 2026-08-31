# 文档地图

冲突时以这份顺序为准：**[`openclaw.yaml`](../.openclaw-hr/config/openclaw.yaml)** → 各域 `SOUL.md` → [项目说明.md](项目说明.md) → [云迁移与记忆交接.md](../.openclaw-hr/docs/云迁移与记忆交接.md)。Skill 细节只在各 `SKILL.md`。

## 按目的读

| 你要做的事 | 读 |
|------------|-----|
| 弄清系统是什么、怎么跑 | [项目说明.md](项目说明.md) |
| clone 后装依赖、起 Gateway / HCM / Canvas | [项目说明.md](项目说明.md) 第 4 节；**包与密钥对照** [环境配置.md](环境配置.md)；步骤细表 [deployment-guide.md](deployment-guide.md) |
| 改某一 HR 域 | 该域 `workspace-*/` 下 `*INTRO.md` 与 `SOUL.md` |
| 入职看板 / HCM API | [`.openclaw-hr/hcm/README.md`](../.openclaw-hr/hcm/README.md) |
| 换云服务器、续飞书会话、防编码失忆 | [云迁移与记忆交接.md](../.openclaw-hr/docs/云迁移与记忆交接.md) |
| 主 / 备 / 测试节点谁干什么 | [三节点职责与工作流程.md](三节点职责与工作流程.md)（分册：[主](nodes/主节点.md) / [备](nodes/备节点.md) / [测试](nodes/测试节点.md)） |
| 比赛脱敏口径 | [脱敏规则.md](脱敏规则.md) |
| 看测过什么、还剩什么 | [全Agent冒烟修复安排](../.openclaw-hr/docs/qa/全Agent冒烟修复安排-2026-08-30.md) 与各 `workspace-*/docs/` |

## 不是现行系统文档

- `_ref/`：旧打包，勿当源码或安装依据。
- `workspace-training/training-materials/`：Agent **生成的课件**，里面的模型名不是本系统配置。
- 根目录 `docs/qa/`：本地测试总册，gitignore，不入库。
