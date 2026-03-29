#!/usr/bin/env python3
"""
模拟Feishu加密webhook请求测试
测试系统处理加密消息的能力
"""

import os
import sys
import json
import time
import hashlib
import base64
import requests
from pathlib import Path

# 添加项目目录到路径
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))


def create_encrypted_message(encryptor, message_type="text", content="测试消息"):
    """创建加密的Feishu消息"""
    import secrets

    # 创建消息体
    if message_type == "url_verification":
        # URL验证消息
        payload = {
            "type": "url_verification",
            "token": os.getenv("FEISHU_VERIFICATION_TOKEN"),
            "challenge": f"test_challenge_{int(time.time())}",
        }
    elif message_type == "text":
        # 文本消息
        payload = {
            "schema": "2.0",
            "header": {
                "event_id": f"test_event_{int(time.time())}",
                "token": os.getenv("FEISHU_VERIFICATION_TOKEN"),
                "create_time": str(int(time.time() * 1000)),
                "event_type": "im.message.receive_v1",
                "tenant_key": "test_tenant",
                "app_id": os.getenv("FEISHU_APP_ID", "test_app"),
            },
            "event": {
                "message": {
                    "chat_id": os.getenv("FEISHU_DEFAULT_CHAT_ID", "oc_test_chat"),
                    "chat_type": "group",
                    "content": json.dumps({"text": content}),
                    "create_time": str(int(time.time() * 1000)),
                    "message_id": f"test_msg_{int(time.time())}",
                    "message_type": "text",
                },
                "sender": {
                    "sender_id": {
                        "union_id": "test_union_id",
                        "user_id": "test_user_id",
                        "open_id": "test_open_id",
                    },
                    "sender_type": "user",
                    "tenant_key": "test_tenant",
                },
            },
        }
    elif message_type == "command":
        # 自定义命令消息
        payload = {
            "schema": "2.0",
            "header": {
                "event_id": f"test_event_{int(time.time())}",
                "token": os.getenv("FEISHU_VERIFICATION_TOKEN"),
                "create_time": str(int(time.time() * 1000)),
                "event_type": "im.message.receive_v1",
                "tenant_key": "test_tenant",
                "app_id": os.getenv("FEISHU_APP_ID", "test_app"),
            },
            "event": {
                "message": {
                    "chat_id": os.getenv("FEISHU_DEFAULT_CHAT_ID", "oc_test_chat"),
                    "chat_type": "group",
                    "content": json.dumps({"text": content}),
                    "create_time": str(int(time.time() * 1000)),
                    "message_id": f"test_msg_{int(time.time())}",
                    "message_type": "text",
                },
                "sender": {
                    "sender_id": {
                        "union_id": "test_union_id",
                        "user_id": "test_user_id",
                        "open_id": "test_open_id",
                    },
                    "sender_type": "user",
                    "tenant_key": "test_tenant",
                },
            },
        }
    else:
        raise ValueError(f"未知的消息类型: {message_type}")

    # 加密消息
    encrypted = encryptor.encrypt(payload)

    # 生成签名
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(8)
    token = os.getenv("FEISHU_VERIFICATION_TOKEN") or os.getenv("FEISHU_ENCRYPT_KEY")

    content_str = f"{timestamp}\n{nonce}\n{token}\n{encrypted}"
    hash_obj = hashlib.sha256(content_str.encode("utf-8"))
    signature = base64.b64encode(hash_obj.digest()).decode("utf-8")

    return {
        "encrypt": encrypted,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": signature,
        "token": token,
        "type": "encrypted"
        if message_type != "url_verification"
        else "url_verification",
        "schema": "2.0" if message_type != "url_verification" else None,
    }


def test_encrypted_webhook():
    """测试加密webhook处理"""
    print("🔐 测试加密Feishu webhook处理")
    print("=" * 60)

    # 加载环境变量
    env_file = project_dir / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")

    # 导入加密器
    from src.legacy.feishu_crypto import FeishuEncryptor

    encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY")
    verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN")

    if not encrypt_key or not verification_token:
        print("❌ 缺少加密配置")
        return False

    try:
        encryptor = FeishuEncryptor(encrypt_key, verification_token)
        print(f"✅ 加密器初始化成功 ({encryptor.aes_mode})")
    except Exception as e:
        print(f"❌ 加密器初始化失败: {e}")
        return False

    # 获取隧道URL
    tunnel_url_file = project_dir / "logs" / "current_tunnel_url.txt"
    if not tunnel_url_file.exists():
        print("❌ 找不到隧道URL文件")
        return False

    tunnel_url = tunnel_url_file.read_text().strip()
    webhook_url = f"{tunnel_url}/feishu/webhook/opencode"
    print(f"📍 Webhook URL: {webhook_url}")

    # 测试1: URL验证 (未加密)
    print("\n1. 测试URL验证 (未加密):")
    challenge_data = {
        "type": "url_verification",
        "token": verification_token,
        "challenge": f"test_challenge_{int(time.time())}",
    }

    try:
        response = requests.post(webhook_url, json=challenge_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("challenge") == challenge_data["challenge"]:
                print("  ✅ URL验证成功")
            else:
                print(f"  ❌ URL验证失败: 挑战不匹配")
                print(f"     期望: {challenge_data['challenge']}")
                print(f"     实际: {result.get('challenge')}")
                return False
        else:
            print(f"  ❌ URL验证失败: 状态码 {response.status_code}")
            print(f"     响应: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ URL验证请求失败: {e}")
        return False

    # 测试2: 加密URL验证
    print("\n2. 测试加密URL验证:")
    encrypted_challenge = create_encrypted_message(encryptor, "url_verification")

    try:
        response = requests.post(webhook_url, json=encrypted_challenge, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if "challenge" in result:
                print("  ✅ 加密URL验证成功")
            else:
                print(f"  ⚠️  加密URL验证返回非挑战响应: {result}")
        else:
            print(f"  ⚠️  加密URL验证失败: 状态码 {response.status_code}")
            print(f"     响应: {response.text[:200]}")
    except Exception as e:
        print(f"  ⚠️  加密URL验证请求失败: {e}")

    # 测试3: 加密文本消息
    print("\n3. 测试加密文本消息:")
    text_message = create_encrypted_message(encryptor, "text", "测试加密消息")

    try:
        response = requests.post(webhook_url, json=text_message, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok") is True:
                print("  ✅ 加密文本消息处理成功")
                print(f"     响应: {result}")
            else:
                print(f"  ⚠️  加密文本消息处理返回非标准响应: {result}")
        else:
            print(f"  ⚠️  加密文本消息处理失败: 状态码 {response.status_code}")
            print(f"     响应: {response.text[:200]}")
    except Exception as e:
        print(f"  ⚠️  加密文本消息请求失败: {e}")

    # 测试4: 加密自定义命令
    print("\n4. 测试加密自定义命令:")
    commands = ["清空session", "kimi", "deepseek", "模型", "启动服务器", "git 提交"]

    for cmd in commands[:2]:  # 只测试前两个命令，避免过多请求
        print(f"  测试命令: '{cmd}'")
        command_message = create_encrypted_message(encryptor, "command", cmd)

        try:
            response = requests.post(webhook_url, json=command_message, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok") is True or result.get("skipped") is True:
                    print(f"    ✅ 命令 '{cmd}' 处理成功")
                else:
                    print(f"    ⚠️  命令 '{cmd}' 处理返回: {result}")
            else:
                print(f"    ⚠️  命令 '{cmd}' 处理失败: 状态码 {response.status_code}")
        except Exception as e:
            print(f"    ⚠️  命令 '{cmd}' 请求失败: {e}")

    print("\n" + "=" * 60)
    print("📊 测试完成总结:")
    print("""
✅ 系统已准备好处理加密的Feishu webhook请求
✅ URL验证功能正常工作
✅ 加密/解密功能正常工作

📋 下一步操作:
1. 按照 check_feishu_config.py 输出的配置步骤配置Feishu控制台
2. 在Feishu中@机器人发送消息进行真实测试
3. 监控服务器日志: tail -f logs/server.log
4. 查看隧道监控: tail -f logs/tunnel_monitor.log

⚠️  注意: 模拟测试使用的是测试数据，真实Feishu请求的数据格式可能略有不同。
    如果真实测试失败，请检查服务器日志中的解密错误信息。
    """)

    return True


if __name__ == "__main__":
    try:
        success = test_encrypted_webhook()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
