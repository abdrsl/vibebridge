#!/usr/bin/env python3
"""
飞书机器人私信配置检查工具
检查机器人是否配置正确以支持私信功能
"""

import os
import sys

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=" * 60)
print("🔍 飞书机器人私信配置检查")
print("=" * 60)

# 检查环境变量
print("\n📋 环境变量检查:")
checks = {
    "FEISHU_APP_ID": "应用 ID",
    "FEISHU_APP_SECRET": "应用密钥",
    "FEISHU_ENCRYPT_KEY": "加密密钥",
    "FEISHU_VERIFICATION_TOKEN": "验证 Token",
}

all_ok = True
for key, name in checks.items():
    value = os.getenv(key)
    if value:
        # 隐藏敏感信息
        masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        print(f"  ✅ {name}: {masked}")
    else:
        print(f"  ❌ {name}: 未设置")
        all_ok = False

# 检查 Webhook 配置
print("\n📡 Webhook 配置检查:")
webhook = os.getenv("FEISHU_BOT_WEBHOOK", "")
if webhook:
    print(f"  ✅ Webhook URL: {webhook[:50]}...")
else:
    print("  ⚠️  Webhook URL: 未设置（使用默认端点）")

# 检查默认聊天 ID
print("\n💬 默认聊天 ID:")
chat_id = os.getenv("FEISHU_DEFAULT_CHAT_ID", "")
if chat_id:
    masked = chat_id[:10] + "..." if len(chat_id) > 10 else chat_id
    print(f"  ✅ {masked}")
else:
    print("  ⚠️  未设置（可选）")

# 提供配置建议
print("\n" + "=" * 60)
print("📖 配置建议")
print("=" * 60)

print("""
如果私信没有输入框，请检查以下飞书开放平台配置：

1. 【能力管理】→【机器人】→ 确保已开启
   https://open.feishu.cn/app/{app_id}/bot

2. 【权限管理】→ 添加以下权限：
   ✅ im:chat:readonly (读取会话)
   ✅ im:message:send (发送消息)
   ✅ im:message.p2p_msg (发送单聊消息) ⭐ 关键！
   ✅ im:message.group_msg (发送群消息)

3. 【事件订阅】→ 配置请求地址：
   URL: {webhook}/feishu/webhook/opencode
   
4. 【事件订阅】→ 添加事件：
   ✅ im.message.receive_v1 (接收消息)

5. 【版本管理与发布】→ 创建版本并发布
   - 版本号: 1.0.0
   - 可用性: 已发布
   - 申请发布并等待审批

6. 【应用功能】→【基础信息】→ 设置可用范围
   - 选择"全部成员"或指定部门

7. 企业管理员在飞书后台添加应用到企业

详细文档: docs/FEISHU_PRIVATE_CHAT_SETUP.md
""")

# 测试连接
print("\n" + "=" * 60)
print("🧪 连接测试")
print("=" * 60)

try:
    import asyncio

    import httpx

    async def test_connection():
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")

        if not app_id or not app_secret:
            print("  ❌ 缺少 App ID 或 App Secret，跳过连接测试")
            return

        print("  🔄 正在获取访问令牌...")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=10.0,
            )

            data = resp.json()
            if data.get("code") == 0:
                print("  ✅ 访问令牌获取成功")
                print(f"  📊 过期时间: {data.get('expire', '未知')} 秒")
            else:
                print(f"  ❌ 获取令牌失败: {data.get('msg', '未知错误')}")
                print(f"     错误码: {data.get('code')}")

    asyncio.run(test_connection())

except ImportError:
    print("  ⚠️  未安装 httpx，跳过连接测试")
    print("     安装: pip install httpx")
except Exception as e:
    print(f"  ❌ 连接测试失败: {e}")

print("\n" + "=" * 60)
print("✨ 检查完成")
print("=" * 60)

if all_ok:
    print("\n✅ 环境变量配置正确！")
    print("\n如果私信仍无输入框，请检查飞书开放平台配置：")
    print("  1. 机器人能力是否开启")
    print("  2. im:message.p2p_msg 权限是否添加")
    print("  3. 应用是否已发布")
    print("  4. 用户是否已添加机器人")
else:
    print("\n❌ 部分环境变量未设置，请检查 .env 文件")
    sys.exit(1)
