name: hr-offer-approval
steps:
  - id: draft
    run: echo '{"candidate":"张三","role":"后端工程师","salary":"28K"}'

  - id: gate
    approval: HR 主管，是否批准这份 Offer 进入下一步发放流程？
    stdin: $draft.stdout

  - id: issue
    run: echo 'Offer 已批准，进入正式发放流程'
    when: $gate.approved
