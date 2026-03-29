"""
测试任务解析模块
"""

import json
from src.legacy.task_parser import extract_text_from_feishu_payload


class TestTaskParser:
    """测试任务解析器"""

    def test_simple_text_payload(self):
        """测试简单的文本payload"""
        payload = {"text": "设计一个桌面线缆整理器"}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "设计一个桌面线缆整理器"
        assert result["status"] == "queued"

    def test_simple_text_empty(self):
        """测试空文本"""
        payload = {"text": ""}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_simple_text_whitespace(self):
        """测试只有空格的文本"""
        payload = {"text": "   "}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_v2_format(self):
        """测试飞书v2格式"""
        payload = {
            "schema": "2.0",
            "header": {
                "event_id": "f1219f57",
                "event_type": "im.message.receive_v1",
                "create_time": "1603723919000000",
                "token": "v2",
                "app_id": "cli_xxx",
                "tenant_key": "xxx",
            },
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_xxx",
                        "union_id": "on_xxx",
                        "user_id": "xxx",
                    },
                    "sender_type": "user",
                    "tenant_key": "xxx",
                },
                "message": {
                    "message_id": "om_xxx",
                    "root_id": "om_xxx",
                    "parent_id": "om_xxx",
                    "create_time": "1603723919000000",
                    "chat_id": "oc_xxx",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": '{"text":"测试v2格式消息"}',
                    "mentions": [],
                },
            },
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "测试v2格式消息"
        assert result["status"] == "queued"

    def test_feishu_v2_format_empty(self):
        """测试飞书v2格式空消息"""
        payload = {
            "schema": "2.0",
            "header": {
                "event_id": "f1219f57",
                "event_type": "im.message.receive_v1",
                "create_time": "1603723919000000",
                "token": "v2",
                "app_id": "cli_xxx",
                "tenant_key": "xxx",
            },
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_xxx",
                        "union_id": "on_xxx",
                        "user_id": "xxx",
                    },
                    "sender_type": "user",
                    "tenant_key": "xxx",
                },
                "message": {
                    "message_id": "om_xxx",
                    "root_id": "om_xxx",
                    "parent_id": "om_xxx",
                    "create_time": "1603723919000000",
                    "chat_id": "oc_xxx",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": '{"text":""}',
                    "mentions": [],
                },
            },
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_v1_format(self):
        """测试飞书v1格式"""
        payload = {
            "event_type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_xxx",
                        "union_id": "on_xxx",
                        "user_id": "xxx",
                    },
                    "sender_type": "user",
                    "tenant_key": "xxx",
                },
                "message": {
                    "message_id": "om_xxx",
                    "root_id": "om_xxx",
                    "parent_id": "om_xxx",
                    "create_time": "1603723919000000",
                    "chat_id": "oc_xxx",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": '{"text":"测试v1格式消息"}',
                    "mentions": [],
                },
            },
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "测试v1格式消息"
        assert result["status"] == "queued"

    def test_feishu_invalid_json_content(self):
        """测试无效的JSON content字段"""
        payload = {
            "event": {
                "message": {
                    "content": "这不是有效的JSON，但包含文本",
                }
            }
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "这不是有效的JSON，但包含文本"
        assert result["status"] == "queued"

    def test_feishu_empty_event(self):
        """测试空event"""
        payload = {"event": {}}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_empty_message(self):
        """测试空message"""
        payload = {"event": {"message": {}}}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_empty_content(self):
        """测试空content"""
        payload = {"event": {"message": {"content": ""}}}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_content_with_whitespace(self):
        """测试只有空格的content"""
        payload = {"event": {"message": {"content": "   "}}}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_json_content_without_text(self):
        """测试JSON content但没有text字段"""
        payload = {
            "event": {
                "message": {
                    "content": '{"other_field": "value"}',
                }
            }
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_feishu_json_content_with_empty_text(self):
        """测试JSON content但text为空"""
        payload = {
            "event": {
                "message": {
                    "content": '{"text": ""}',
                }
            }
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "unknown"
        assert result["raw_text"] == ""
        assert result["status"] == "ignored"

    def test_help_message_detection(self):
        """测试help消息检测（虽然解析器不直接处理，但确保能正确解析）"""
        payload = {"text": "help"}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "help"
        assert result["status"] == "queued"

    def test_complex_design_request(self):
        """测试复杂的设计请求"""
        design_request = "设计一个适合PETG材料3D打印的桌面线缆整理器，要求：1. 有多个线缆通道 2. 可调节分隔板 3. 底部有防滑垫 4. 外观简洁现代"
        payload = {"text": design_request}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == design_request
        assert result["status"] == "queued"

    def test_payload_with_extra_fields(self):
        """测试带有额外字段的payload"""
        payload = {"text": "测试消息", "extra_field": "额外值", "another_field": 123}

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "测试消息"
        assert result["status"] == "queued"

    def test_nested_feishu_structure(self):
        """测试嵌套的飞书结构"""
        payload = {
            "schema": "2.0",
            "header": {"event_id": "test"},
            "event": {
                "sender": {"sender_id": {"open_id": "test"}},
                "message": {
                    "message_id": "test",
                    "content": json.dumps({"text": "嵌套结构测试"}),
                    "mentions": [{"key": "value"}],
                },
            },
        }

        result = extract_text_from_feishu_payload(payload)

        assert result["task_type"] == "design_request"
        assert result["raw_text"] == "嵌套结构测试"
        assert result["status"] == "queued"
