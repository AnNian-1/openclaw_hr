#!/usr/bin/env bash
# 入职跟进 review 脚本 —— running-onboarding-review Skill 的核心脚本
# 由 Cron 在入职后第 7/30/60/90 天定时触发，也可手动跑。
# 用法: onboarding-review.sh <候选人姓名> <入职天数> [pinyin]
#
# 数据来源：HCM 系统 API（只读）
# 不写入 HCM、不写本地 review-state——review 记录由 HR/主管在 HCM 维护。
# 本脚本只查询状态、生成报告，供小慧通知 HR/主管。
set -euo pipefail

NAME="${1:-新员工}"
DAY="${2:-7}"
PINYIN="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOW="$(date '+%Y-%m-%d %H:%M')"

# 按入职天数确定本次 review 的跟进重点
case "$DAY" in
  7)  FOCUS="完成公司级 Onboarding;导师启动带教;融入团队" ;;
  30) FOCUS="部门岗位培训;HR 第一次新人关怀沟通" ;;
  60) FOCUS="带教进展检查;岗位胜任度初评" ;;
  90) FOCUS="导师带教结束;6 个月试用期者中期反馈" ;;
  *)  FOCUS="常规跟进" ;;
esac

# 从 HCM API 读取候选人信息 + 5 个准备节点状态 + review 状态
# 退出码：0 查到；4 花名册无此人；5 HCM 不可用。不写 review-state。
set +e
HCM_RESULT="$(python3 - "$SCRIPT_DIR" "$NAME" "$PINYIN" "$DAY" "$FOCUS" "$NOW" <<'PY'
import json, sys, os
sys.path.insert(0, sys.argv[1])
import hcm_api

name, pinyin_hint, day, focus, now = sys.argv[2:7]

hcm_ok, matches, hcm_err = hcm_api.find_candidates(
    name=name if not pinyin_hint else None,
    pinyin=pinyin_hint or None,
)
if pinyin_hint and hcm_ok and not matches:
    hcm_ok, matches, hcm_err = hcm_api.find_candidates(pinyin=pinyin_hint)
if hcm_ok and not matches and name:
    hcm_ok, matches, hcm_err = hcm_api.find_candidates(name=name)

if not hcm_ok:
    print(json.dumps({
        "found": False,
        "hcm_ok": False,
        "error": "HCM 不可用，无法做入职跟进",
        "detail": hcm_err,
    }, ensure_ascii=False))
    sys.exit(5)

if not matches:
    print(json.dumps({
        "found": False,
        "hcm_ok": True,
        "error": f"花名册中未找到「{name}」" + (f"（拼音 {pinyin_hint}）" if pinyin_hint else ""),
    }, ensure_ascii=False))
    sys.exit(4)

if len(matches) > 1:
    pins = [c.get("pinyin") for c in matches]
    print(json.dumps({
        "found": False,
        "hcm_ok": True,
        "error": f"「{name}」匹配多名候选人 {pins}，请手传拼音",
    }, ensure_ascii=False))
    sys.exit(4)

candidate = matches[0]

pinyin = candidate.get("pinyin", "")
hcm_status = candidate.get("status", "")

# 5 个准备节点
nodes = candidate.get("nodes") or []
node_map = {n["node_type"]: n for n in nodes}
prep = {}
for key in ("contract", "account", "device", "training", "buddy"):
    n = node_map.get(key, {})
    data = n.get("data") or {}
    prep[key] = {
        "status": n.get("status", "未就绪"),
        "detail": data.get("status", ""),
    }

# review 状态
reviews = candidate.get("reviews") or []
review_map = {r["review_type"]: r for r in reviews}
day_key = f"day{day}"
review_rec = review_map.get(day_key, {})
review_status = review_rec.get("status", "pending")
review_content = review_rec.get("content", "")

result = {
    "found": True,
    "name": candidate.get("name"),
    "pinyin": pinyin,
    "role": candidate.get("role", ""),
    "salary": candidate.get("salary", ""),
    "hcm_status": hcm_status,
    "day": int(day),
    "focus": focus,
    "reviewed_at": now,
    "prep_nodes": prep,
    "review_status": review_status,
    "review_content": review_content,
    "all_reviews": {r.get("review_type"): r.get("status") for r in reviews},
}

# 判断是否需要提醒 HR
needs_attention = []
if review_status == "completed":
    result["action"] = "already_reviewed"
    result["message"] = f"第 {day} 天 review 已由 HR/主管完成"
else:
    result["action"] = "needs_review"
    # 检查准备节点是否都就绪
    pending_nodes = [k for k, v in prep.items() if v["status"] not in ("completed", "已审批", "已通过", "已配齐", "已匹配", "已排期")]
    if pending_nodes:
        needs_attention.append(f"以下准备节点未完成: {', '.join(pending_nodes)}")
    result["message"] = f"第 {day} 天 review 待触发，重点: {focus}"
    if needs_attention:
        result["warnings"] = needs_attention

print(json.dumps(result, ensure_ascii=False, indent=2))
PY
)"
PY_RC=$?
set -e
if [ "$PY_RC" -ne 0 ]; then
  echo "[review] ❌ $HCM_RESULT" >&2
  exit "$PY_RC"
fi
FOUND="$(echo "$HCM_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('found', False))" 2>/dev/null || echo "False")"
if [ "$FOUND" != "True" ]; then
  echo "[review] ❌ $HCM_RESULT" >&2
  exit 4
fi

# 输出结构化报告到 stdout（供小慧解析后通知 HR）
echo "$HCM_RESULT"

# 人话摘要到 stderr
python3 - "$HCM_RESULT" "$NAME" "$DAY" <<'PY' >&2
import json, sys
data = json.loads(sys.argv[1])
name, day = sys.argv[2], int(sys.argv[3])

print("=" * 40)
print(f" 入职跟进 Review · 第 {day} 天")
print(f" 候选人：{data['name']}（{data['pinyin']}）")
print(f" 岗位：{data['role']} · 薪资：{data['salary']}")
print(f" HCM 状态：{data['hcm_status']}")
print("=" * 40)
print(f"本次跟进重点：{data['focus']}")
print("-" * 40)
print("入职准备 5 节点状态（来自 HCM）：")
for key, label in [("contract","合同"), ("account","IT 账号"), ("device","设备"), ("buddy","Buddy"), ("training","培训")]:
    n = data["prep_nodes"].get(key, {})
    print(f"  {label:8s} {n.get('status', '未就绪')}")
print("-" * 40)
print(f"Review 状态：{data['review_status']}")
if data.get("review_content"):
    print(f"Review 内容：{data['review_content']}")
print("-" * 40)
action = data.get("action", "")
if action == "already_reviewed":
    print(f"✅ {data['message']}")
elif action == "needs_review":
    print(f"⚠️  {data['message']}")
    if data.get("warnings"):
        for w in data["warnings"]:
            print(f"   ⚠ {w}")
print("=" * 40)
PY
