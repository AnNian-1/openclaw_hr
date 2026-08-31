#!/usr/bin/env bash
# 入职跟进 review 脚本 —— running-onboarding-review Skill 的核心脚本
# 由 Cron 在入职后第 7/30/60/90 天定时触发，也可手动跑。
# 用法: onboarding-review.sh <候选人姓名> <入职天数> [pinyin]
#
# 数据来源：HCM 花名册 + 五部门准备节点（只读）；review 状态读本地 review-state/reviews.json
# 到点只催办，不自动标完成；HR 确认后由小慧执行 review-store.sh mark-done
set -euo pipefail

NAME="${1:-新员工}"
DAY="${2:-7}"
PINYIN="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PREPEND_NODE="$(cd "$SCRIPT_DIR/../../../.." && pwd)/scripts/prepend-node22.sh"
# shellcheck disable=SC1090
[ -f "$_PREPEND_NODE" ] && . "$_PREPEND_NODE"
NOW="$(date '+%Y-%m-%d %H:%M')"

case "$DAY" in
  7|30|60|90) ;;
  *)
    echo "[onboarding-review] 非法入职天数 '$DAY'（只允许 7/30/60/90）" >&2
    exit 2
    ;;
esac

# 按入职天数确定本次 review 的跟进重点
case "$DAY" in
  7)  FOCUS="完成公司级 Onboarding;导师启动带教;融入团队" ;;
  30) FOCUS="部门岗位培训;HR 第一次新人关怀沟通" ;;
  60) FOCUS="带教进展检查;岗位胜任度初评" ;;
  90) FOCUS="导师带教结束;6 个月试用期者中期反馈" ;;
  *)  FOCUS="常规跟进" ;;
esac

# 从 HCM 读花名册与准备节点；从本地表读 review 状态
# 退出码：0 查到；4 花名册无此人；5 HCM 不可用
set +e
HCM_RESULT="$(python3 - "$SCRIPT_DIR" "$NAME" "$PINYIN" "$DAY" "$FOCUS" "$NOW" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import hcm_api
import review_store

name, pinyin_hint, day, focus, now = sys.argv[2:7]
day = int(day)

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
cand_name = candidate.get("name") or name

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

# review 状态（本地表）。未 ensure 则不算已开通跟进。
review_rec = review_store.get(pinyin, day) or {}
if review_rec:
    review_store.touch_triggered(pinyin, day)
    review_rec = review_store.get(pinyin, day) or review_rec
review_status = review_rec.get("status", "pending")
review_content = review_rec.get("content") or ""
review_focus = review_rec.get("focus") or focus
armed = review_store.is_armed(pinyin)

result = {
    "found": True,
    "name": cand_name,
    "pinyin": pinyin,
    "role": candidate.get("role", ""),
    "salary": candidate.get("salary", ""),
    "hcm_status": hcm_status,
    "day": day,
    "focus": review_focus,
    "reviewed_at": now,
    "prep_nodes": prep,
    "review_status": review_status,
    "review_content": review_content,
    "all_reviews": review_store.all_reviews_map(pinyin),
    "review_source": "local",
    "reviews_armed": armed,
}

needs_attention = []
pending_nodes = [k for k, v in prep.items() if v["status"] != "completed"]
if not armed:
    result["action"] = "not_armed"
    result["message"] = "试用期跟进尚未开通：HCM 五节点须全部 completed"
    if pending_nodes:
        needs_attention.append(f"尚未完成的部门节点: {', '.join(pending_nodes)}")
        result["warnings"] = needs_attention
elif review_status == "completed":
    result["action"] = "already_reviewed"
    result["message"] = f"第 {day} 天 review 已由 HR/主管完成"
else:
    result["action"] = "needs_review"
    if pending_nodes:
        needs_attention.append(f"以下准备节点未完成: {', '.join(pending_nodes)}")
    result["message"] = f"第 {day} 天 review 待触发，重点: {review_focus}"
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
elif action == "not_armed":
    print(f"⏸  {data['message']}")
    if data.get("warnings"):
        for w in data["warnings"]:
            print(f"   ⚠ {w}")
elif action == "needs_review":
    print(f"⚠️  {data['message']}")
    if data.get("warnings"):
        for w in data["warnings"]:
            print(f"   ⚠ {w}")
print("=" * 40)
PY
