# report-system

小慧出报只读 **HCM 已冻结** 月报。冻结在 HCM：`POST /api/reports/monthly/{YYYY-MM}/freeze` 或 `python hcm/backend/freeze_monthly.py --period YYYY-MM`。

`tests/fixtures/monthly-report/` 仅 HCM demo seed / 测试，生产脚本不读 CSV。
