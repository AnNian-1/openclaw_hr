"""冻结快照 / 出报脚本使用的中文列名。禁止经 /api/nodes 回写这些汇总列。"""

# (中文列, 英文属性, 类型)
FUNNEL_COLS = [
    ("月份", "month", "str"),
    ("投递数", "applications", "int"),
    ("初筛通过", "screen_pass", "int"),
    ("面试", "interviews", "int"),
    ("Offer", "offers", "int"),
    ("入职", "hired", "int"),
    ("投递转初筛率", "screen_rate", "str"),
    ("面试转Offer率", "interview_to_offer_rate", "str"),
    ("Offer接受率", "offer_accept_rate", "str"),
]

POSITIONS_COLS = [
    ("岗位", "job_title", "str"),
    ("所属类别", "category", "str"),
    ("HC", "hc", "int"),
    ("已入职", "hired", "int"),
    ("在招中", "recruiting", "int"),
    ("平均在招天数", "avg_days", "int"),
    ("招聘状态", "status", "str"),
]

RETENTION_COLS = [
    ("月份", "month", "str"),
    ("入职人数", "hired_count", "int"),
    ("试用期通过", "probation_pass", "int"),
    ("试用期未通过", "probation_fail", "int"),
    ("45天内离职", "leave_45d", "int"),
    ("45天内离职率", "leave_45d_rate", "str"),
    ("备注", "note", "str"),
]

TRAINING_COLS = [
    ("月份", "month", "str"),
    ("应参训人数", "expected", "int"),
    ("完成人数", "completed", "int"),
    ("完成率", "rate", "str"),
    ("培训满意度", "satisfaction", "float"),
    ("主要培训内容", "content", "str"),
]

COST_COLS = [
    ("月份", "month", "str"),
    ("招聘渠道费用", "channel_cost", "int"),
    ("入职人数", "hired_count", "int"),
    ("人均招聘成本", "cost_per_hire", "int"),
    ("平均TimeToHire天数", "tth_days", "int"),
    ("主要费用构成", "breakdown", "str"),
]

ATTRITION_COLS = [
    ("月份", "month", "str"),
    ("离职总人数", "total", "int"),
    ("主动离职", "voluntary", "int"),
    ("被动离职", "involuntary", "int"),
    ("月离职率", "monthly_rate", "str"),
    ("薪资原因", "reason_salary", "int"),
    ("发展原因", "reason_growth", "int"),
    ("管理原因", "reason_mgmt", "int"),
    ("家庭原因", "reason_family", "int"),
    ("不胜任", "reason_unfit", "int"),
]


def zh_to_en_kwargs(row: dict, cols: list) -> dict:
    out = {}
    for zh, en, kind in cols:
        raw = row[zh]
        if kind == "int":
            out[en] = int(raw)
        elif kind == "float":
            out[en] = float(raw)
        else:
            out[en] = "" if raw is None else str(raw)
    return out


def model_to_zh(obj, cols: list) -> dict:
    out = {}
    for zh, en, _kind in cols:
        out[zh] = getattr(obj, en)
    return out
