#!/usr/bin/env bash
# 现场核对分权：从 Gateway 日志 logs/gateway.log 取最近几次「收到的消息」，
# 先按 credentials/feishu-default-allowFrom.json 判是否已配对，
# 再用 scripts/hr-data-access.sh 判身份，回 er-admin 会话里找这条消息触发的 exec，
# 打印「网关给出的发送人 → 身份 → 调用的命令 → 闸门结果 → HCM 是否读取」，
# 最后列出 credentials/feishu-pairing.json 里的待配对请求。只读，不改任何状态。
#
# 为什么不用 `openclaw pairing list feishu`：不 source env.sh 时它读的是默认 profile
# ~/.openclaw（requests 恒为空），不是 HR 的 .openclaw-hr，会静默给出 0 条。
# 这里直接读 HR profile 落盘的那份文件。
#
# 用法: bash demo/show-gate.sh [条数，默认 3]
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$(cd "$HERE/.." && pwd)"
N="${1:-3}"

python3 - "$STATE/logs/gateway.log" "$STATE/agents/er-admin/sessions" "$HERE/scripts/hr-data-access.sh" \
  "$STATE/credentials/feishu-default-allowFrom.json" "$STATE/credentials/feishu-pairing.json" "$N" <<'PY'
import glob, json, os, re, subprocess, sys
from datetime import datetime

log_path, sess_dir, gate, allow_path, pair_path = sys.argv[1:6]
n = int(sys.argv[6])
short = lambda s: re.sub(r'ou_([0-9a-f]{4})[0-9a-f]+', r'ou_\1…', s or '')
LABEL = {'hr': 'HR', 'denied': '已登记 · 非 HR', 'unknown': '未登记', 'demo': '无发送人'}
ANSI = re.compile(r'\x1b\[[0-9;]*m')
TS = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z))')
RECV = re.compile(r'received message from (ou_[0-9a-f]{32}) in ')
DM = re.compile(r'DM from (ou_[0-9a-f]{32}): (.*)$')


def stamp(ts):
    """gateway.log 行首时间戳本身就是本机时区（+08:00），直接截取显示。"""
    return ts[5:19].replace('T', ' ')


def secs(ts):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return 0.0


def allowed_ids():
    try:
        with open(allow_path, encoding='utf-8') as fh:
            return set(json.load(fh).get('allowFrom') or []), None
    except (OSError, ValueError) as e:
        return set(), str(e)


def pairing_reqs():
    try:
        with open(pair_path, encoding='utf-8') as fh:
            return json.load(fh).get('requests') or [], None
    except (OSError, ValueError) as e:
        return None, str(e)


def gate_role(sender):
    out = subprocess.run(['bash', gate, 'role', sender], capture_output=True, text=True)
    return out.stdout.strip()


ALLOWED, allow_err = allowed_ids()


def ident(snd):
    """先看飞书网关这一层（配没配对），再看闸门这一层（登没登记）。

    未配对账号这里按演示口径显示为「员工」。这个标签不对应任何登记文件：
    闸门名单 hr-data-access.sh 和 permission-roles.yaml 里都没有它。
    要和文件保持一致，把下面的 '员工' 改回 '未配对'。
    """
    if allow_err is None and snd not in ALLOWED:
        return '员工'
    r = gate_role(snd)
    return LABEL.get(r, r)


# 1) Gateway 日志里最近 n 条收到的消息。未配对的账号只有 received 行、没有 DM 正文。
msgs, cur = [], None
for raw in open(log_path, encoding='utf-8', errors='replace'):
    line = ANSI.sub('', raw).rstrip('\n')
    hit = TS.match(line)
    if not hit:
        continue
    m = RECV.search(line)
    if m:
        if cur:
            msgs.append(cur)
        cur = {'ts': hit.group(1), 'sender': m.group(1), 'text': ''}
        continue
    m = DM.search(line)
    if m and cur and cur['sender'] == m.group(1) and not cur['text']:
        cur['text'] = m.group(2).strip()
if cur:
    msgs.append(cur)
msgs = msgs[-n:]

# 2) er-admin 会话里，每条用户消息之后跟着的 exec（payroll-query / monthly-report）
records = []
files = sorted((f for f in glob.glob(os.path.join(sess_dir, '*.jsonl')) if '.trajectory.' not in f),
               key=os.path.getmtime)[-20:]
for f in files:
    rec, calls = None, {}
    for line in open(f, encoding='utf-8', errors='replace'):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        m = o.get('message') or {}
        r = m.get('role')
        if r == 'user':
            text = ''.join(c.get('text', '') for c in m.get('content', []) if isinstance(c, dict))
            hit = re.search(r'"sender_id":\s*"(ou_[0-9a-f]{32})"', text)
            body = re.findall(r'ou_[0-9a-f]{32}:\s*(.+)', text, re.S)
            rec = {'ts': o.get('timestamp', ''), 'sender': hit.group(1) if hit else '',
                   'body': body[-1].strip() if body else '', 'calls': []}
            records.append(rec)
            calls = {}
        elif r == 'assistant' and rec is not None:
            for c in m.get('content', []):
                if c.get('type') != 'toolCall' or c.get('name') != 'exec':
                    continue
                cmd = (c.get('arguments') or {}).get('command', '')
                if 'payroll-query' in cmd or 'monthly-report' in cmd:
                    calls[c['id']] = cmd
        elif r == 'toolResult' and m.get('toolCallId') in calls:
            d = m.get('details') or {}
            rec['calls'].append((calls.pop(m['toolCallId']), d.get('exitCode'), d.get('aggregated', '')))


def find(msg):
    """按发送人 + 正文匹配会话记录；正文对不上就退回同发送人 120s 内最近一条。"""
    cands = [r for r in records if r['sender'] == msg['sender']]
    if not cands:
        return None
    if msg['text']:
        exact = [r for r in cands if r['body'] == msg['text']]
        if exact:
            return min(exact, key=lambda r: abs(secs(r['ts']) - secs(msg['ts'])))
    best = min(cands, key=lambda r: abs(secs(r['ts']) - secs(msg['ts'])))
    return best if abs(secs(best['ts']) - secs(msg['ts'])) <= 120 else None


if allow_err:
    print(f'⚠ 读不到已配对名单，身份只按闸门判断：{allow_err}\n')
if not msgs:
    print(f'日志里还没有收到消息：{log_path}')

for msg in msgs:
    snd = msg['sender']
    print(f"[{stamp(msg['ts'])}] 网关给出的发送人：{short(snd)}  →  {ident(snd)}")
    rec = find(msg)
    if rec is None:
        print('  数据：未读取（未配对，消息没交给 Agent）')
        print()
        continue
    if not rec['calls']:
        print('  数据：未读取（没走闸门的消息，无调用记录）')
        print()
        continue
    for cmd, code, out in rec['calls']:
        passed = re.search(r'--sender\s+(\S+)', cmd)
        passed = passed.group(1) if passed else ''
        first = out.strip().splitlines()[0] if out.strip() else ''
        denied = first.startswith('{"allowed":false')
        gate_line = first if denied else '{"allowed":true}'
        print(f'  调用命令：{short(cmd.replace("bash scripts/", ""))}')
        if passed and passed != snd:
            print('  ⚠ 命令里的 --sender 与网关给出的发送人不一致')
        print(f'  闸门结果：{gate_line}    退出码 {code}')
        if denied:
            print('  数据：未读取（闸门之后的查询脚本没有运行）')
        elif code == 0:
            try:
                res = json.loads(out[out.index('{'):out.rindex('}') + 1])
                hit = '；'.join(f"{p.get('name')} · {p.get('role')} · {p.get('salary')}"
                               for p in res.get('people', [])[:3]) + f"（来源 {res.get('source')}）"
            except ValueError:
                hit = out.strip().splitlines()[-1][:60]
            print(f'  数据：已读取  {hit}')
        else:
            print('  数据：闸门放行，查询出错')
    print()

print('飞书待配对请求（未配对账号的消息停在这里，没交给 Agent）：')
reqs, pair_err = pairing_reqs()
if pair_err:
    print(f'  ⚠ 读不到待配对文件：{pair_err}')
elif not reqs:
    print('  （无）')
else:
    for r in reqs:
        print('  ' + short(str(r.get('id') or '')) + '  配对码 ' + str(r.get('code', '')))
PY
