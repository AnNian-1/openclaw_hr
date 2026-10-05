# 行政 · 现行必须对齐（更新 INTRO 时不得写成课程旧状）

- 飞书私聊/群 @ **直达** `er-admin`，不经过 router。WebChat / CLI 才走总控再转来。
- 政策必须 IMA 原文；无命中或凭证缺失，禁止用模型常识编制度。
- 飞书非 HR：**不能**查他人工资、**不能**出月报。飞书 HR / WebChat / CLI 可以查花名册合同薪资、可补跑月报。
- 月报数字由 pandas 从 6 个 CSV 算出，模型不改数字。生产月末任务走 OpenClaw cron 任务 `hr-monthly-report-push`（5.12 / 18790，月末 23:59），exec 入口 `scripts/er-admin-run.sh monthly-report-push`。`er-admin-cron` 为该任务专用 agent。
- 月报 Python 以 conda `openclaw-hr` + prepend 为准；手册若仍写 `py312`，以现行运维口径为准。
- 五类 HiTL：本人薪资考勤个税、个案争议、劳动仲裁、知识库无依据、要破例审批。
- 子 Agent 不能互相 spawn。
