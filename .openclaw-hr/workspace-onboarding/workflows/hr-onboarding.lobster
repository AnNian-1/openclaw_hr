name: hr-onboarding
# 星桥科技 · 新员工入职审批工作流
# 设计依据：hr-wiki《09-入职流程》—— Offer 接受 → 入职准备 → 报到当天 → 入职后跟进
# 4 路并行：合同 / IT 账号 / 设备 / 培训 四条准备工作并行推进
# 2 个 HiTL 审批门：合同审批、账号权限审批 —— 关键节点暂停等真人批准
# 账号/设备申请为本地 stub（不接真实 IT 系统），由 stub-system/ 下脚本模拟
#
# 注意：Lobster 的 approval: 字段不做 ${arg} 模板替换。
# 候选人专属审批信息走 run 步骤产出 JSON（run 会做模板替换），
# JSON 里带 prompt 字段，Lobster 用它作为审批问题。

args:
  name:
    default: 新员工
  pinyin:
    default: employee
  role:
    default: 工程师
  salary:
    default: 面议

env:
  STUB: /root/.openclaw-hr/workspace-onboarding/stub-system
  STATE: /root/.openclaw-hr/workspace-onboarding/stub-state

steps:
  # ── 节点 1 · 4 路并行准备 ──────────────────────────────
  # 合同 / IT 账号 / 设备 / 培训 四条工作并行推进
  # 用 shell 后台任务 + wait 实现真实并发：四个 stub 同时跑
  - id: prep
    run: |
      echo "=== 入职准备启动：${name}（${role}）==="
      ( bash "$STUB/contract.sh"   "${name}" "${role}" "${salary}" ) &
      ( bash "$STUB/it-account.sh" "${name}" "${pinyin}" ) &
      ( bash "$STUB/device.sh"     "${name}" ) &
      ( bash "$STUB/training.sh"   "${name}" ) &
      wait
      echo "=== 4 路并行准备全部完成 ==="

  # ── 节点 2 · HiTL 审批门 1：合同审批 ───────────────────
  # 合同条款关乎法律责任，必须 HR 主管点头才能进入签约
  # run 步骤产出带 prompt 的 JSON —— Lobster 用 json.prompt 作为审批问题
  - id: contract_gate
    run: |
      cat "$STATE/contract.json" | python3 -c 'import json,sys; c=json.load(sys.stdin); print(json.dumps({"prompt":"HR 主管，请审批 "+c["candidate"]+" 的劳动合同：岗位 "+c["role"]+" / 薪资 "+c["salary"]+" / 试用期 "+c["probation"]+"。是否批准进入签约？","items":[c]},ensure_ascii=False))'
    approval: true

  # ── 节点 3 · HiTL 审批门 2：账号权限审批 ────────────────
  # 账号开通后即拥有系统访问权限，权限范围必须人工核准
  - id: account_gate
    run: |
      cat "$STATE/account.json" | python3 -c 'import json,sys; a=json.load(sys.stdin); print(json.dumps({"prompt":"IT 安全负责人，请审批 "+a["candidate"]+" 的账号权限范围（工号 "+a["workno"]+" / 邮箱 "+a["email"]+" / 企业微信 + 内网访问）。是否批准开通？","items":[a]},ensure_ascii=False))'
    approval: true

  # ── 节点 4 · Buddy 匹配（审批通过后执行）────────────────
  # 只有合同与账号都批准，才为新员工匹配带教 Buddy
  - id: buddy
    run: bash "$STUB/buddy.sh" "${name}" "${role}"
    when: $contract_gate.approved && $account_gate.approved

  # ── 节点 5 · 入职流程归档（全部审批通过才执行）──────────
  - id: complete
    run: |
      echo "=== ${name} 入职审批工作流完成 ==="
      echo "合同审批：已通过 | 账号权限审批：已通过"
      echo "[归档] 合同 / 账号 / 设备 / 培训 / Buddy 五项就绪，等待报到当天签约"
    when: $contract_gate.approved && $account_gate.approved
