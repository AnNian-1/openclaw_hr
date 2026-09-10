#!/bin/bash
# 权限分级检查脚本
# 用法: ./check-permission.sh <sender_id> <action>

SENDER_ID="$1"
ACTION="$2"
CONFIG_FILE="config/permission-roles.yaml"

if [ -z "$SENDER_ID" ] || [ -z "$ACTION" ]; then
    echo '{"error": "用法: ./check-permission.sh <sender_id> <action>"}'
    exit 1
fi

# 检查是否为管理员
is_admin() {
    grep -q "$SENDER_ID" "$CONFIG_FILE" && grep -A 10 "^admin:" "$CONFIG_FILE" | grep -q "$SENDER_ID"
}

# 检查是否为HR专员
is_hr_staff() {
    grep -q "$SENDER_ID" "$CONFIG_FILE" && grep -A 10 "^hr_staff:" "$CONFIG_FILE" | grep -q "$SENDER_ID"
}

# 获取用户角色
get_role() {
    if is_admin; then
        echo "admin"
    elif is_hr_staff; then
        echo "hr_staff"
    else
        echo "employee"
    fi
}

# 检查权限
ROLE=$(get_role)

case "$ACTION" in
    "query_policy")
        # 所有角色都可以查询政策
        echo '{"allowed": true, "role": "'$ROLE'", "action": "query_policy"}'
        ;;
    "generate_monthly_report"|"query_payroll")
        # 空 sender 视为演示（WebChat/CLI）；飞书以 hr-data-access.sh 为准
        if [ -z "$SENDER_ID" ] || [ "$SENDER_ID" = "*" ]; then
            echo '{"allowed": true, "role": "demo", "action": "'$ACTION'"}'
        elif [ "$ROLE" = "admin" ] || [ "$ROLE" = "hr_staff" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "'$ACTION'"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "'$ACTION'", "reason": "飞书非 HR 不能查他人工资或出月报"}'
        fi
        ;;
    "view_audit_log")
        # 只有HR专员和管理员可以查看审计日志
        if [ "$ROLE" = "admin" ] || [ "$ROLE" = "hr_staff" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "view_audit_log"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "view_audit_log", "reason": "权限不足：需要HR专员或管理员权限"}'
        fi
        ;;
    "manage_knowledge_base")
        # 只有HR专员和管理员可以管理知识库
        if [ "$ROLE" = "admin" ] || [ "$ROLE" = "hr_staff" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "manage_knowledge_base"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "manage_knowledge_base", "reason": "权限不足：需要HR专员或管理员权限"}'
        fi
        ;;
    "gateway_config")
        # 只有管理员可以修改Gateway配置
        if [ "$ROLE" = "admin" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "gateway_config"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "gateway_config", "reason": "权限不足：需要管理员权限"}'
        fi
        ;;
    "manage_skills")
        # 只有管理员可以管理Skill
        if [ "$ROLE" = "admin" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "manage_skills"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "manage_skills", "reason": "权限不足：需要管理员权限"}'
        fi
        ;;
    "manage_users")
        # 只有管理员可以管理用户角色
        if [ "$ROLE" = "admin" ]; then
            echo '{"allowed": true, "role": "'$ROLE'", "action": "manage_users"}'
        else
            echo '{"allowed": false, "role": "'$ROLE'", "action": "manage_users", "reason": "权限不足：需要管理员权限"}'
        fi
        ;;
    *)
        echo '{"error": "未知操作: '$ACTION'"}'
        exit 1
        ;;
esac
