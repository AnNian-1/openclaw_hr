name: hr-onboarding
# 星桥科技 · 新员工入职审批工作流
# 设计依据：hr-wiki《09-入职流程》—— Offer 接受 → 入职准备 → 报到当天 → 入职后跟进
# 4 路并行：合同 / IT 账号 / 设备 / 培训 四条准备工作并行推进
# 2 个 HiTL 审批门：合同审批、账号权限审批 —— 关键节点暂停等真人批准
# 账号/设备申请为本地 stub（不接真实 IT 系统），由本 Skill scripts/ 下脚本模拟
#
# 注意 1：Lobster 的 approval: 字段不做 ${arg} 模板替换。
#   候选人专属审批信息走 run 步骤产出 JSON（run 会做模板替换），
#   JSON 里带 prompt 字段，Lobster 用它作为审批问题。
#
# 注意 2：本工作流文件被 running-onboarding-workflow Skill 封装。
#   $STUB / $STATE / $STUB_STATE_DIR / $WORKSPACE 四个路径不在本文件写死，
#   而是由启动包装脚本 scripts/run-onboarding.sh 在调 lobster 前 export 进环境——
#   lobster 默认会把启动器 export 的这些环境变量透传到每个 run 子 shell。
#   $STUB 指向本 Skill 自己的 scripts/ 目录，
#   $STATE 指向 workspace 根的 stub-state/（review、看板两个下游 Skill 都要读它），
#   $STUB_STATE_DIR 指向 $STATE/<pinyin>/（候选人隔离目录），
#   $WORKSPACE 指向 workspace 根（record-pending-approval.py 落盘 pending-approvals 用）。
#
# 注意 3：stub 输出落到 $STUB_STATE_DIR = $STATE/<pinyin>/ —— run-onboarding.sh 在调 lobster
#   前 export STUB_STATE_DIR="$STATE/$PINYIN"。每个候选人独立子目录，并发入职互不冲突。
#
# 注意 4：每个候选人目录下有 workflow.json（由 update-workflow.py 维护），
#   记录 5 个主节点扭转事件 + 当前状态 + halt 时间，供查询 Skill / 看板读取。
#   不要在 lobster 文件里写 env 块试图"显式注入"——${STUB} 不会被替换，
#   会作为字面字符串覆盖外部真值。

args:
  name:
    default: 新员工
  pinyin:
    default: employee
  role:
    default: 工程师
  salary:
    default: 面议

steps:
  # ── 节点 1 · 4 路并行准备 ──────────────────────────────
  # 合同 / IT 账号 / 设备 / 培训 四条工作并行推进
  # 用 shell 后台任务 + wait 实现真实并发：四个 stub 同时跑
  # stub 输出落到 $STUB_STATE_DIR = $STATE/<pinyin>/（候选人目录隔离，由 run-onboarding.sh 注入）
  - id: prep
    run: |
      python3 "$STUB/update-workflow.py" init "${pinyin}" "${name}" "${role}" "${salary}"
      echo "=== 入职准备启动：${name}（${role}, ${pinyin}）==="
      ( bash "$STUB/contract.sh"   "${name}" "${role}" "${salary}" ) &
      ( bash "$STUB/it-account.sh" "${name}" "${pinyin}" ) &
      ( bash "$STUB/device.sh"     "${name}" ) &
      ( bash "$STUB/training.sh"   "${name}" ) &
      wait
      python3 "$STUB/update-workflow.py" event "${pinyin}" prep completed "4 路并行准备全部完成"
      echo "=== 4 路并行准备全部完成 ==="

  # ── 节点 2 · HiTL 审批门 1：合同审批 ───────────────────
  # 合同条款关乎法律责任，必须 HR 主管点头才能进入签约
  # run 步骤做四件事（顺序）：
  #   0. contract.sh —— 进门前刷新 stub-state/<pinyin>/contract.json（updated_at=此刻）
  #   1. record-pending-approval.py <gate> ${pinyin} 落盘"halt 时"stub 快照到
  #      $WORKSPACE/pending-approvals/<pinyin>-<gate>.json——给查询 Skill 提供对比基线
  #   2. update-workflow.py event … halted —— 写 workflow.json（当前状态 + 停留起点）
  #   3. build-approval-prompt.py <gate> ${pinyin} 现拼 prompt（含时间戳后缀），输出给 Lobster
  # Lobster 用 json.prompt 作为审批问题；approval: true 触发 halt + resumeToken
  # 进门 status=待审批（等真人批）；通过后才写已通过——看板据此区分「准备好了」vs「已批过」
  - id: contract_gate
    run: |
      bash "$STUB/contract.sh" "${name}" "${role}" "${salary}" "待审批"
      python3 "$STUB/record-pending-approval.py" contract "${pinyin}"
      python3 "$STUB/update-workflow.py" event "${pinyin}" contract_gate halted "等待 HR 主管审批合同"
      python3 "$STUB/build-approval-prompt.py"   contract "${pinyin}"
    approval: true

  # ── 节点 3 · HiTL 审批门 2：账号权限审批 ────────────────
  # 账号开通后即拥有系统访问权限，权限范围必须人工核准
  # 能跑到这里说明 contract_gate 已批准——合同改已通过，本门三份落盘用待审批，再记 halted
  # 本门保鲜范围与 build-approval-prompt / record-pending-approval 一致：
  #   account + device + training（进门前必须重跑对应 shell，刷新 updated_at）
  - id: account_gate
    run: |
      python3 "$STUB/update-workflow.py" event "${pinyin}" contract_gate approved "合同审批已通过"
      bash "$STUB/contract.sh"   "${name}" "${role}" "${salary}" "已通过"
      bash "$STUB/it-account.sh" "${name}" "${pinyin}" "待审批"
      bash "$STUB/device.sh"     "${name}"
      bash "$STUB/training.sh"   "${name}"
      bash "$STUB/buddy.sh"      "${name}" "${role}"
      python3 "$STUB/record-pending-approval.py" account "${pinyin}"
      python3 "$STUB/update-workflow.py" event "${pinyin}" account_gate halted "等待 IT 安全审批账号"
      python3 "$STUB/build-approval-prompt.py"   account "${pinyin}"
    approval: true

  # ── 节点 4 · Buddy 匹配（审批通过后执行）────────────────
  # 只有合同与账号都批准，才为新员工匹配带教 Buddy
  - id: buddy
    run: |
      python3 "$STUB/update-workflow.py" event "${pinyin}" account_gate approved "账号权限审批已通过"
      bash "$STUB/it-account.sh" "${name}" "${pinyin}" "已通过"
      bash "$STUB/buddy.sh" "${name}" "${role}"
      python3 "$STUB/update-workflow.py" event "${pinyin}" buddy completed "Buddy 匹配完成"
    when: $contract_gate.approved && $account_gate.approved

  # ── 节点 5 · 入职流程归档（全部审批通过才执行）──────────
  # 归档后注册 7/30/60/90 天一次性 Cron（--at），到点由 onboarding Agent 跑 review
  - id: complete
    run: |
      set -euo pipefail
      echo "=== ${name} 入职审批工作流完成 ==="
      echo "合同审批：已通过 | 账号权限审批：已通过"
      echo "[归档] 合同 / 账号 / 设备 / 培训 / Buddy 五项就绪，等待报到当天签约"
      # 流程完成：清掉本候选人的 pending-approvals 快照，否则查询 Skill 会把"已走完的门"误报成仍在 halt
      rm -f "$WORKSPACE/pending-approvals/${pinyin}-contract.json" \
            "$WORKSPACE/pending-approvals/${pinyin}-account.json"
      echo "[归档] 已清理 pending-approvals/${pinyin}-* 审批快照"
      python3 "$STUB/update-workflow.py" event "${pinyin}" complete completed "入职审批工作流完成"
      # 完成钩子：按入职日注册 4 个一次性 review Cron；失败则归档失败（勿吞掉）
      bash "$WORKSPACE/skills/running-onboarding-review/scripts/schedule-onboarding-reviews.sh" \
            "${name}" "${pinyin}"
      echo "[归档] 已注册 7/30/60/90 天入职跟进 Cron"
    when: $contract_gate.approved && $account_gate.approved
