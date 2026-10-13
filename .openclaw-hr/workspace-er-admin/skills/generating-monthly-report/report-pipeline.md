# 月报 Pipeline 细则

Skill **只编排发布**。数字来自 HCM 已冻结快照 `source=HCM`。

1. 宿主机判断明天是否 1 号（上海时间）。
2. `POST /api/reports/monthly/{YYYY-MM}/freeze`（幂等，不覆盖既有 run）。
3. 生成脚本只读同一月份 GET；文件名月份必须与请求一致。
4. 发布失败可重试，不能改 HCM 冻结数字。
5. 无冻结或事实不足：停止，不读 CSV、不填 0。
