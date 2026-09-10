入职跟进运行时目录。总表是本目录 `reviews.json`（由 `sync-reviews-if-ready.sh` / `review-store.sh` / Cron 催办维护 `records` 与 `armed`）。

不要再依赖 `review-<姓名>-day<N>.json`。看板与查询都读 `reviews.json`。

当前夹具以 HCM 花名册为准（常见：员工1 / yuangong1）。QA 备份见 `$OPENCLAW_STATE_DIR/fixtures/onboarding-review-state/`。
