#!/usr/bin/env python3
"""
测试审核机器人C的功能
"""

import asyncio
import os
import sys

import aiohttp

# 添加到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.approval.manager import approval_manager


async def test_approval_system():
    """测试审批系统"""
    print("=" * 50)
    print("🤖 审核机器人C 功能测试")
    print("=" * 50)

    # 1. 创建审批请求
    print("\n1. 创建审批请求...")
    request = approval_manager.create_approval(
        user_id="ou_REDACTED_OPEN_ID",
        command="git push origin main",
        description="提交代码到主分支",
        risk_level="high",
        source="test"
    )
    print(f"   ✅ 创建成功: {request.approval_id}")
    print(f"   📋 命令: {request.command}")
    print(f"   🎚️  风险: {request.risk_level}")

    # 2. 查询审批状态
    print("\n2. 查询审批状态...")
    fetched = approval_manager.get_approval(request.approval_id)
    print(f"   ✅ 查询成功: {fetched.status.value}")

    # 3. 列出待审批
    print("\n3. 列出待审批请求...")
    pending = approval_manager.list_pending()
    print(f"   ✅ 待审批数量: {len(pending)}")

    # 4. 模拟飞书卡片构建
    print("\n4. 构建飞书卡片...")
    from src.approval.manager import FeishuApprovalCardBuilder
    card = FeishuApprovalCardBuilder.build_approval_card(request)
    print("   ✅ 卡片构建成功")
    print(f"   📊 卡片元素数: {len(card.get('elements', []))}")

    # 5. 模拟批准
    print("\n5. 模拟审批通过...")
    approved = approval_manager.approve(
        request.approval_id,
        "ou_REDACTED_OPEN_ID",
        "测试批准"
    )
    print(f"   ✅ 审批完成: {approved.status.value}")

    # 6. 构建结果卡片
    print("\n6. 构建结果卡片...")
    result_card = FeishuApprovalCardBuilder.build_result_card(approved)
    print("   ✅ 结果卡片构建成功")

    # 7. 测试API端点
    print("\n7. 测试API端点...")
    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        # 测试创建审批
        async with session.post(
            f"{base_url}/api/approval/create",
            json={
                "user_id": "ou_test",
                "command": "deploy production",
                "description": "部署到生产环境",
                "risk_level": "critical"
            }
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                if result.get("success"):
                    print(f"   ✅ API创建审批成功: {result.get('approval_id')}")
                else:
                    print(f"   ❌ API创建失败: {result.get('error')}")
            else:
                print(f"   ⚠️  API返回状态码: {resp.status}")

        # 测试查询待审批
        async with session.get(f"{base_url}/api/approval/pending/list") as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"   ✅ API查询待审批成功: {result.get('count')} 个")
            else:
                print(f"   ⚠️  API返回状态码: {resp.status}")

    print("\n" + "=" * 50)
    print("✅ 所有测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_approval_system())
