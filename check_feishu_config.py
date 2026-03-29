#!/usr/bin/env python3
"""
Feishu配置检查脚本
检查当前Feishu配置状态和系统就绪情况
"""

import os
import sys
import json
import requests
from pathlib import Path

# 添加项目目录到路径
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))


def check_env_vars():
    """检查环境变量配置"""
    print("🔍 检查环境变量配置...")

    required_vars = [
        "FEISHU_ENCRYPT_KEY",
        "FEISHU_VERIFICATION_TOKEN",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
    ]

    optional_vars = ["DEEPSEEK_API_KEY", "TUNNEL_TYPE", "FEISHU_DEFAULT_CHAT_ID"]

    print("\n📋 必需环境变量:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ❌ {var}: 未设置")

    print("\n📋 可选环境变量:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked}")
        else:
            print(f"  ⚠️  {var}: 未设置 (可选)")

    return True


def check_server_status():
    """检查服务器状态"""
    print("\n🔍 检查服务器状态...")

    try:
        # 检查本地服务器
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(
                f"  ✅ 本地服务器: 运行中 (多智能体系统: {data.get('multi_agent_system', False)})"
            )
            return True
        else:
            print(f"  ❌ 本地服务器: 响应异常 (状态码: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 本地服务器: 无法连接 ({e})")
        return False


def check_tunnel_status():
    """检查隧道状态"""
    print("\n🔍 检查隧道状态...")

    # 读取当前隧道URL
    tunnel_url_file = project_dir / "logs" / "current_tunnel_url.txt"
    if not tunnel_url_file.exists():
        print("  ❌ 隧道URL文件不存在 (logs/current_tunnel_url.txt)")
        return False

    tunnel_url = tunnel_url_file.read_text().strip()
    if not tunnel_url:
        print("  ❌ 隧道URL为空")
        return False

    print(f"  📍 隧道URL: {tunnel_url}")

    try:
        response = requests.get(f"{tunnel_url}/", timeout=10)
        if response.status_code == 200:
            print(
                f"  ✅ 隧道: 可访问 (状态: {response.json().get('status', 'unknown')})"
            )

            # 检查webhook端点
            webhook_url = f"{tunnel_url}/feishu/webhook/opencode"
            print(f"  📍 Webhook端点: {webhook_url}")
            return True
        else:
            print(f"  ❌ 隧道: 响应异常 (状态码: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 隧道: 无法访问 ({e})")
        return False


def check_encryption_config():
    """检查加密配置"""
    print("\n🔍 检查加密配置...")

    from src.legacy.feishu_crypto import get_encryptor

    encryptor = get_encryptor()
    if encryptor:
        print(f"  ✅ 加密器: 可用 ({encryptor.aes_mode})")
        print(f"  📊 密钥长度: {encryptor.key_length} 字节")

        # 测试加密/解密
        try:
            test_data = {"test": "encryption", "timestamp": "1234567890"}
            encrypted = encryptor.encrypt(test_data)
            decrypted = encryptor.decrypt(encrypted)

            if decrypted.get("test") == "encryption":
                print("  ✅ 加密/解密: 功能正常")
                return True
            else:
                print("  ❌ 加密/解密: 数据完整性验证失败")
                return False
        except Exception as e:
            print(f"  ❌ 加密/解密测试失败: {e}")
            return False
    else:
        print("  ❌ 加密器: 不可用 (检查环境变量)")
        return False


def generate_feishu_config_instructions():
    """生成Feishu控制台配置说明"""
    print("\n📋 Feishu控制台配置步骤:")
    print("=" * 60)

    # 读取隧道URL
    tunnel_url_file = project_dir / "logs" / "current_tunnel_url.txt"
    if tunnel_url_file.exists():
        tunnel_url = tunnel_url_file.read_text().strip()
        webhook_url = f"{tunnel_url}/feishu/webhook/opencode"
    else:
        webhook_url = "https://your-tunnel-url/feishu/webhook/opencode"

    encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "your_encrypt_key")
    verification_token = os.getenv(
        "FEISHU_VERIFICATION_TOKEN", "your_verification_token"
    )

    print(f"""
1. 登录飞书开发者控制台: https://open.feishu.cn/app

2. 选择应用: {os.getenv("FEISHU_APP_ID", "your_app_id")}

3. 进入"事件订阅"页面:

4. 配置请求URL:
   - URL: {webhook_url}
   - Verification Token: {verification_token}
   - Encrypt Key: {encrypt_key}
   - 启用加密: ✅ ON

5. 订阅事件:
   - im.message.receive_v1 (接收消息)

6. 权限配置 (进入"权限管理"):
   - ✅ im:message (发送和接收消息)
   - ✅ im:message:send_as_bot (以机器人身份发送消息)

7. 保存并发布版本

8. 测试配置:
   - 在飞书中@机器人发送消息
   - 检查服务器日志: tail -f logs/server.log
   - 查看隧道监控: tail -f logs/tunnel_monitor.log
    """)

    print("=" * 60)


def main():
    """主函数"""
    print("🚀 Feishu配置状态检查")
    print("=" * 60)

    # 加载环境变量
    env_file = project_dir / ".env"
    if env_file.exists():
        print(f"📄 加载环境变量: {env_file}")
        # 简单加载.env文件
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")

    results = {
        "环境变量": check_env_vars(),
        "服务器状态": check_server_status(),
        "隧道状态": check_tunnel_status(),
        "加密配置": check_encryption_config(),
    }

    print("\n" + "=" * 60)
    print("📊 检查结果汇总:")

    all_passed = True
    for check, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {check}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有检查通过！系统已准备好处理Feishu webhook请求。")
        generate_feishu_config_instructions()
    else:
        print("⚠️  部分检查未通过，请根据以上信息进行修复。")
        print("   详细配置指南: docs/FEISHU_SETUP.md")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
