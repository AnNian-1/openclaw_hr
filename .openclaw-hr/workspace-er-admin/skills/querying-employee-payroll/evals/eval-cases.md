# 评测 · querying-employee-payroll

| 场景 | 命令 | 验收 |
|---|---|---|
| WebChat/CLI 查别人 | `er-admin-run.sh payroll-query --name 员工1` | exit 0，`salary` 与花名册/stub 一致 |
| 飞书 HR | 同上加 `--sender ou_960b054220a76c956acf80e0d9b025b8` | exit 0 |
| 飞书员工 | `--sender ou_66cfc2fa5b3142c6b232fc9114fc7b94 --name 员工1` | exit 3，无薪资数字 |
| 花名册没有的人 | `--name 不存在的人` | exit 4，不编造 |
