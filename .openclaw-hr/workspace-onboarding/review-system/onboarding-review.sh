#!/usr/bin/env bash
# 入职跟进 review 脚本 —— running-onboarding-review Skill 的核心脚本
# 由 Cron 在入职后第 7/30/60/90 天定时触发，也可手动跑。
# 用法: onboarding-review.sh <候选人姓名> <入职天数> [pinyin]
# 读入职工作流落盘的 stub-state/<pinyin>/ 真实状态 + 09-入职流程.md 的跟进事项,
# 产出一份结构化 review 报告,落盘到 workspace 根的 review-state/。
set -euo pipefail

NAME="${1:-新员工}"
DAY="${2:-7}"
PINYIN="${3:-}"

# ── 路径推导：本脚本封进 Skill 后，位于
#    <workspace>/skills/running-onboarding-review/scripts/onboarding-review.sh
#    ——向上三级即 workspace 根。stub-state / review-state 都在 workspace 根，
#    是入职工作流、看板共享的数据资产，不放在本 Skill 目录里。
#    支持 $ONBOARDING_WORKSPACE 环境变量覆盖，便于测试与移植。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ONBOARDING_WORKSPACE:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
STATE_ROOT="$WORKSPACE/stub-state"
OUT="$WORKSPACE/review-state"
mkdir -p "$OUT"
NOW="$(date '+%Y-%m-%d %H:%M')"

# 解析候选人目录：显式拼音 > 扫 stub-state/*/workflow.json|contract.json 的 candidate
resolve_pinyin () {
  local name="$1" hint="$2"
  if [ -n "$hint" ] && [ -d "$STATE_ROOT/$hint" ]; then
    echo "$hint"
    return 0
  fi
  python3 - "$STATE_ROOT" "$name" <<'PY'
import json, os, sys
root, name = sys.argv[1], sys.argv[2]
matches = []
if not os.path.isdir(root):
    sys.exit(0)
for entry in sorted(os.listdir(root)):
    base = os.path.join(root, entry)
    if not os.path.isdir(base):
        continue
    for fn in ("workflow.json", "contract.json", "account.json"):
        path = os.path.join(base, fn)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        cand = d.get("candidate") or d.get("name")
        if cand == name:
            matches.append(entry)
            break
# 去重保序
seen, out = set(), []
for m in matches:
    if m not in seen:
        seen.add(m)
        out.append(m)
if len(out) == 1:
    print(out[0])
elif len(out) > 1:
    sys.stderr.write(f"[review] 「{name}」匹配到多个目录 {out}，请手传拼音\n")
PY
}

PINYIN="$(resolve_pinyin "$NAME" "$PINYIN" || true)"
if [ -z "${PINYIN}" ]; then
  echo "[review] 找不到候选人「${NAME}」的 stub-state/<pinyin>/ 目录。" >&2
  echo "[review] 请确认入职工作流已落盘，或手传拼音：onboarding-review.sh ${NAME} ${DAY} <pinyin>" >&2
  # 仍产出 review 记录，但 5 节点一律未就绪（保持旧行为可见）
  STATE_DIR=""
else
  STATE_DIR="$STATE_ROOT/$PINYIN"
  echo "[review] 读取落盘目录：stub-state/${PINYIN}/"
fi

# 按入职天数确定本次 review 的跟进事项(对应 09-入职流程.md 第四节)
case "$DAY" in
  7)  FOCUS="完成公司级 Onboarding;导师启动带教;融入团队" ;;
  30) FOCUS="部门岗位培训;HR 第一次新人关怀沟通" ;;
  60) FOCUS="带教进展检查;岗位胜任度初评" ;;
  90) FOCUS="导师带教结束;6 个月试用期者中期反馈" ;;
  *)  FOCUS="常规跟进" ;;
esac

# 从 stub-state/<pinyin>/ 读 5 个准备节点（候选人隔离目录）
read_status () {
  local key="$1"
  if [ -z "$STATE_DIR" ]; then
    echo "未就绪"
    return
  fi
  python3 -c "import json; print(json.load(open('$STATE_DIR/$key.json')).get('status','缺失'))" 2>/dev/null || echo "未就绪"
}
C_STAT="$(read_status contract)"
A_STAT="$(read_status account)"
D_STAT="$(read_status device)"
B_STAT="$(read_status buddy)"
T_STAT="$(read_status training)"

# 人类可读报告
echo "========================================"
echo " 入职跟进 Review · 第 ${DAY} 天"
echo " 候选人：${NAME}${PINYIN:+（${PINYIN}）}"
echo " 触发时间：${NOW}"
echo "========================================"
echo "本次跟进重点：${FOCUS}"
echo "----------------------------------------"
echo "入职准备 5 节点状态（来自入职工作流）："
echo "  合同     ${C_STAT}"
echo "  IT 账号  ${A_STAT}"
echo "  设备     ${D_STAT}"
echo "  Buddy    ${B_STAT}"
echo "  培训     ${T_STAT}"
echo "----------------------------------------"
echo "Review 结论：第 ${DAY} 天跟进已执行，重点 [${FOCUS}] 已提醒。"

# 结构化状态落盘,供 HTML 看板读取(文件名带候选人名,多人入职不冲突)
python3 - "$NAME" "$DAY" "$FOCUS" "$NOW" "$OUT" "${PINYIN:-}" \
  "$C_STAT" "$A_STAT" "$D_STAT" "$B_STAT" "$T_STAT" <<'PY'
import json, sys
name, day, focus, now, out, pinyin = sys.argv[1:7]
c, a, d, b, t = sys.argv[7:12]
rec = {
    "candidate": name,
    "pinyin": pinyin or None,
    "day": int(day),
    "focus": focus,
    "reviewedAt": now,
    "status": "已跟进",
    "prep_nodes": {
        "contract": c,
        "account": a,
        "device": d,
        "buddy": b,
        "training": t,
    },
}
with open(f"{out}/review-{name}-day{day}.json", "w", encoding="utf-8") as f:
    json.dump(rec, f, ensure_ascii=False, indent=2)
PY
echo "[review] 状态已落盘 review-state/review-${NAME}-day${DAY}.json"
