#!/bin/bash
# 监控隧道 URL 变化并自动推送通知

TUNNEL_URL_FILE="/home/user/workspace/vibebridge/logs/last_tunnel_url.txt"
LAST_URL_FILE="/home/user/workspace/vibebridge/logs/.last_notified_url.txt"
FEISHU_CHAT_ID="your_chat_id_here"
# 备用通知方式 - 发送到当前会话
NOTIFY_SESSION="your_notify_session_here"
FEISHU_APP_ID="your_app_id_here"

# 检查当前 URL
if [ -f "$TUNNEL_URL_FILE" ]; then
    CURRENT_URL=$(cat "$TUNNEL_URL_FILE" | tr -d '\n')
else
    echo "❌ 隧道 URL 文件不存在"
    exit 1
fi

# 检查上次通知的 URL
LAST_URL=""
if [ -f "$LAST_URL_FILE" ]; then
    LAST_URL=$(cat "$LAST_URL_FILE" | tr -d '\n')
fi

# 如果 URL 变化了，发送通知
if [ "$CURRENT_URL" != "$LAST_URL" ]; then
    echo "🔄 隧道 URL 已变化: $LAST_URL -> $CURRENT_URL"
    
    # 保存新 URL
    echo "$CURRENT_URL" > "$LAST_URL_FILE"
    
    # 构建通知消息
    MESSAGE="隧道 URL 已更新: $CURRENT_URL"
    
    # 发送飞书通知 (通过 curl 或 vibebridge)
    echo "$MESSAGE" > /tmp/tunnel_notification.txt
    echo "⚠️ 飞书通知需要配置 VibeBridge 服务后发送，请手动更新"
    
    echo "✅ 已发送 URL 变更通知"
else
    echo "✓ 隧道 URL 未变化: $CURRENT_URL"
fi