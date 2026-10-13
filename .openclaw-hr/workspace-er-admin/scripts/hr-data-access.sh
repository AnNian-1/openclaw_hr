#!/usr/bin/env bash
# 行政敏感数据闸门：花名册薪资查询、对话出月报。
# 允许：飞书 HR、无 sender（WebChat / CLI / 演示 *）。
# 拒绝：已登记的飞书主管 / 员工 / owner。未知 ou_ 也拒绝。
#
# 用法:
#   hr-data-access.sh check [sender]
#   hr-data-access.sh role [sender]
# 退出: 0 允许 · 3 拒绝 · 2 用法错
set -euo pipefail        # -e 任一命令非零即退出；-u 引用未定义变量报错；-o pipefail 管道任一段失败即整体失败

HR_ID="ou_960b054220a76c956acf80e0d9b025b8"        # 唯一白名单：飞书 HR 的 open_id
# 主管 / 员工 / owner（与 openclaw.yaml toolsBySender 同一批 ou_）
DENY_IDS=$'ou_85759e2571f33307b6fc7b265060d5c1\nou_66cfc2fa5b3142c6b232fc9114fc7b94\nou_a8cf75f38e774b2c1a5c79117004d965'        # $'…' 是 ANSI-C 引号，\n 转成真换行 → 三个 id 各占一行，供下面 grep -x 做整行匹配

normalize_sender() {        # 把各种写法的发送人 ID 归一化成裸 ou_；只整理字符串，不判权限
  local raw="${1:-}"        # 取第 1 个参数，没传就是空串；${1:-} 同时避开 set -u
  raw="${raw#"${raw%%[![:space:]]*}"}"        # 剥前导空白：内层 %% 只留下开头的空白串，外层 # 把这个前缀删掉
  raw="${raw%"${raw##*[![:space:]]}"}"        # 剥尾随空白：内层 ## 只留下结尾的空白串，外层 % 把这个后缀删掉
  raw="${raw#id:}"        # 剥 "id:" 前缀（toolsBySender 键型的写法）
  raw="${raw#user:}"        # 剥 "user:" 前缀（飞书私聊 peer 的写法）
  raw="${raw#channel:feishu:}"        # 剥 "channel:feishu:" 前缀（必须排在下一条之前，否则前半段会被 "feishu:" 先啃掉）
  raw="${raw#feishu:}"        # 剥 "feishu:" 前缀（网关 from 字段的写法）
  printf '%s' "$raw"        # 不带换行输出，方便上层用 $(...) 精确捕获，不沾多余空白
}

classify() {        # 判定发送人属于哪一类，结果打到 stdout
  local s
  s="$(normalize_sender "${1:-}")"        # 先归一化，再比
  if [ -z "$s" ] || [ "$s" = "*" ] || [ "$s" = "webchat" ] || [ "$s" = "cli" ] || [ "$s" = "demo" ]; then        # 空 / 通配 / 三种非飞书来源 = 无发送人语境
    echo "demo"        # 类 1：WebChat、CLI、现场演示
    return        # 提前返回，不再往下比
  fi
  if [ "$s" = "$HR_ID" ]; then        # 字符串全等比较，不是正则
    echo "hr"        # 类 2：飞书 HR
    return
  fi
  if printf '%s\n' "$DENY_IDS" | grep -qxF "$s"; then        # 把三行名单喂给 grep：-q 静默只回退出码 · -x 整行相等 · -F 当纯字符串不当正则
    echo "denied"        # 类 3：已登记但无权
    return
  fi
  echo "unknown"        # 类 4：兜底——压根没登记过的 ou_（denied 和 unknown 在下游待遇相同，都只判"非 hr|demo"）
}

cmd="${1:-}"        # 子命令：check / role
sender="${2:-}"        # 发送人，可省略
case "$cmd" in
  role)        # 只回答"他属于哪一类"，不判放行
    classify "$sender"
    ;;        # 到此结束，脚本退出码取自 classify，正常为 0
  check)        # 判放行：输出 JSON，用退出码表达结论
    role="$(classify "$sender")"        # 先分类，结果存下来给下面两个分支共用
    case "$role" in
      hr|demo)
        echo "{\"allowed\":true,\"role\":\"$role\"}"        # JSON 手拼；$role 只可能是那四个字面量，无需转义
        exit 0        # 放行
        ;;
      *)
        echo "{\"allowed\":false,\"role\":\"$role\",\"reason\":\"飞书非 HR 不能查他人工资或出月报\"}"
        exit 3        # 拒绝：调用方 er-admin-run.sh 靠这个 3 拦住后面的真脚本
        ;;
    esac
    ;;
  *)
    echo "usage: hr-data-access.sh check|role [sender]" >&2
    exit 2        # 用法错，与"拒绝(3)"分开，便于区分是写错了还是被挡了
    ;;
esac
