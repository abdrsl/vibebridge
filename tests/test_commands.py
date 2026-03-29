#!/usr/bin/env python3
"""
测试自定义命令
"""

import json
import asyncio
import sys

sys.path.insert(0, ".")

from src.legacy.command_processor import get_command_processor


async def test_commands():
    processor = get_command_processor()
    print(f"Loaded {len(processor.commands)} commands")
    for cmd_name, config in processor.commands.items():
        print(f"\n--- Testing command: {cmd_name} ---")
        print(f"Config: {json.dumps(config, ensure_ascii=False, indent=2)}")
        # Simulate match
        match = processor.match_command(cmd_name)
        if match:
            print(f"Match success")
            # Execute command (requires chat_id and user_id)
            # Use dummy IDs
            result = await processor.execute_command(
                match, chat_id="oc_test_chat", user_id="ou_test_user"
            )
            print(f"Result: {result}")
        else:
            print(f"Match failed")


if __name__ == "__main__":
    asyncio.run(test_commands())
