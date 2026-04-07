#!/usr/bin/env python3
"""
测试飞书API权限
检查机器人是否有发送、删除消息的权限
"""

import asyncio
import time

from src.legacy.feishu_client import feishu_client


async def test_feishu_permissions():
    """测试飞书API权限"""
    print("=== 测试飞书API权限 ===")
    print()

    # 1. 测试获取access token
    print("1. 测试获取Access Token")
    print("-" * 40)
    token = await feishu_client.get_tenant_access_token()
    if token:
        print(f"✅ 成功获取Access Token: {token[:20]}...")
        print(f"   当前时间: {time.time()}")
        print(f"   Token过期时间: {feishu_client._token_expires_at}")
        print(f"   剩余有效期: {feishu_client._token_expires_at - time.time():.0f}秒")
    else:
        print("❌ 获取Access Token失败")
        print("   可能的原因:")
        print("   - FEISHU_APP_ID 或 FEISHU_APP_SECRET 配置错误")
        print("   - 应用凭证无效或已过期")
        print("   - 网络连接问题")
        return

    print()

    # 2. 测试发送文本消息
    print("2. 测试发送文本消息")
    print("-" * 40)
    test_chat_id = "oc_REDACTED_CHAT_ID"  # 测试聊天ID
    test_message = "🔍 飞书API权限测试消息\n\n这是一条测试消息，用于验证机器人是否有发送消息的权限。"

    print(f"聊天ID: {test_chat_id}")
    print(f"消息长度: {len(test_message)} 字符")

    send_result = await feishu_client.send_text_message(test_chat_id, test_message)
    print(f"发送结果: {send_result}")

    if send_result and send_result.get("code") == 0:
        print("✅ 发送文本消息成功")
        message_id = send_result.get("data", {}).get("message_id")
        print(f"   消息ID: {message_id}")

        # 3. 测试删除消息
        print()
        print("3. 测试删除消息")
        print("-" * 40)
        if message_id:
            print(f"删除消息ID: {message_id}")
            delete_result = await feishu_client.delete_message(message_id)
            print(f"删除结果: {delete_result}")

            if delete_result and delete_result.get("code") == 0:
                print("✅ 删除消息成功")
            else:
                print("❌ 删除消息失败")
                print("   错误信息:")
                print(f"   Code: {delete_result.get('code')}")
                print(f"   Msg: {delete_result.get('msg')}")
                print(f"   Data: {delete_result.get('data')}")
                print("   可能的原因:")
                print("   - 机器人没有删除消息的权限 (im:message:delete)")
                print("   - 消息不存在或已被删除")
                print("   - 权限配置错误")
        else:
            print("⚠️ 无法获取消息ID，跳过删除测试")
    else:
        print("❌ 发送文本消息失败")
        print("   错误信息:")
        print(f"   Code: {send_result.get('code') if send_result else 'N/A'}")
        print(f"   Msg: {send_result.get('msg') if send_result else 'N/A'}")
        print(f"   Data: {send_result.get('data') if send_result else 'N/A'}")
        print("   可能的原因:")
        print("   - 机器人没有发送消息的权限 (im:message)")
        print("   - 机器人不在该聊天中或已被禁言")
        print("   - Access Token权限不足")
        print("   - 聊天ID错误")

    print()
    print("4. 权限检查建议")
    print("-" * 40)
    print("请检查飞书开放平台中的机器人权限配置:")
    print("✅ 必需的权限:")
    print("   - im:message         # 发送消息")
    print("   - im:message:read    # 接收消息")
    print("   - im:message:delete  # 删除消息（用于实时更新）")
    print("   - im:message:update  # 更新消息（可选，用于卡片更新）")
    print()
    print("🔍 检查步骤:")
    print("   1. 登录飞书开放平台")
    print("   2. 找到你的应用")
    print("   3. 进入「权限管理」页面")
    print("   4. 确保上述权限已申请并审核通过")
    print("   5. 发布新版本并等待审核（如需）")

    print()
    print("=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_feishu_permissions())
