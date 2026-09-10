---
name: querying-employee-payroll
description: Look up another employee's contract salary from the HCM roster (fallback to onboarding stub-state). Use when HR on Feishu, or anyone on WebChat/CLI, asks what someone else is paid, 查工资, 合同薪资, or 花名册薪资. Do not invent names or amounts. Feishu manager/employee senders are denied by the script.
metadata:
  openclaw:
    requires:
      bins: ["bash"]
---

# querying-employee-payroll

按花名册查出**别人的合同薪资**。数字只来自 HCM `GET /api/candidates`，HCM 不可用时才读入职 `stub-state` 里已有的人。禁止编姓名、禁止编金额。

这是演示用的数据可见性，不是发薪系统，也不是政策答疑。

## 何时用

- WebChat / CLI：「员工1工资多少」「花名册里谁拿多少」
- 飞书 **HR**（`ou_2f67ed66e57e214e72c318a57c60d1c4`）问别人的合同薪资
- 不要用本 Skill 回答政策（走 `answering-hr-policy-questions`）
- 不要用本 Skill 出月报（走 `generating-monthly-report`）

## 身份

`exec` 必须走壳脚本，并把飞书 `ou_` **原样**传给 `--sender`。WebChat / CLI 没有 `ou_` 时不要编造，省略 `--sender`。

```bash
# 飞书 HR
bash scripts/er-admin-run.sh payroll-query --sender ou_2f67ed66e57e214e72c318a57c60d1c4 --name 员工1

# WebChat / CLI
bash scripts/er-admin-run.sh payroll-query --name 员工1
bash scripts/er-admin-run.sh payroll-query --all
```

脚本对主管 / 员工 / owner 的 `ou_` 直接拒绝（退出码 3）。**禁止**把别人的 `ou_` 改成 HR 的来绕过。

## 怎么答

1. 先跑脚本，只念返回 JSON 里的 `people[]`。
2. `ok=false` / 退出码 4：说花名册没有此人，**不要补一个数**。
3. 关键字段原样引用：`name` / `role` / `salary`，并说明 `source`（`hcm` 或 `stub-fallback`）。
4. 带上 disclaimer：演示合同薪资，不是工资条明细。

## 不做什么

- 不查考勤、个税、实发、年假余额（花名册没有这些字段）。
- 飞书非 HR 问「我的工资少了 800」：不要走本 Skill，按政策 Skill 第 1 类升级人工。
- 不向 HCM 写入。
