#!/usr/bin/env python3
"""
Unit tests for WebSocket event processor
Tests event format conversion and processing logic
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_websocket import OpenCodeEventProcessor


class TestWebSocketEventProcessor(unittest.TestCase):
    """Test OpenCodeEventProcessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.message_processor = OpenCodeEventProcessor("im.message.receive_v1")
        self.card_processor = OpenCodeEventProcessor("card.action.trigger")
        
        # Sample test events
        self.sample_sdk_v2_event = {
            "schema": "2.0",
            "header": {
                "event_id": "test_event_v2_001",
                "event_type": "im.message.receive_v1",
                "create_time": "2026-04-01T03:00:00Z",
                "token": "test_token_v2",
                "app_id": "test_app_v2",
                "tenant_key": "test_tenant_v2"
            },
            "event": {
                "message": {
                    "message_id": "msg_v2_001",
                    "chat_id": "oc_test_chat_v2",
                    "content": '{"text": "test message v2"}'
                },
                "sender": {
                    "sender_id": {
                        "open_id": "user_v2_001"
                    }
                }
            }
        }
        
        self.sample_sdk_v1_event = {
            "uuid": "test_uuid_v1",
            "token": "test_token_v1",
            "ts": "2026-04-01T03:00:00Z",
            "event": {
                "type": "im.message.receive_v1",
                "message": {
                    "message_id": "msg_v1_001",
                    "chat_id": "oc_test_chat_v1",
                    "content": '{"text": "test message v1"}'
                },
                "sender": {
                    "sender_id": {
                        "open_id": "user_v1_001"
                    }
                }
            }
        }
        
        self.sample_card_event = {
            "schema": "2.0",
            "header": {
                "event_id": "test_card_event_001",
                "event_type": "card.action.trigger",
                "create_time": "2026-04-01T03:00:00Z",
                "token": "test_token_card",
                "app_id": "test_app_card",
                "tenant_key": "test_tenant_card"
            },
            "event": {
                "action": {
                    "value": '{"action": "confirm", "session_id": "test_session"}'
                },
                "operator": {
                    "open_id": "user_card_001"
                }
            }
        }

    def test_type_method(self):
        """Test type() method returns dict"""
        self.assertEqual(self.message_processor.type(), dict)
        self.assertEqual(self.card_processor.type(), dict)

    def test_convert_to_webhook_format_v2(self):
        """Test conversion of SDK v2 format to webhook format"""
        result = self.message_processor._convert_to_webhook_format(self.sample_sdk_v2_event)
        
        # Should return unchanged for v2 format
        self.assertEqual(result, self.sample_sdk_v2_event)
        self.assertEqual(result["schema"], "2.0")
        self.assertEqual(result["header"]["event_id"], "test_event_v2_001")
        self.assertEqual(result["event"]["message"]["message_id"], "msg_v2_001")

    def test_convert_to_webhook_format_v1(self):
        """Test conversion of SDK v1 format to webhook format"""
        result = self.message_processor._convert_to_webhook_format(self.sample_sdk_v1_event)
        
        # Should convert to v1 schema format
        self.assertEqual(result["schema"], "1.0")
        self.assertEqual(result["header"]["event_type"], "im.message.receive_v1")
        self.assertEqual(result["event"]["message"]["message_id"], "msg_v1_001")
        self.assertEqual(result["header"]["token"], "test_token_v1")
        self.assertEqual(result["header"]["create_time"], "2026-04-01T03:00:00Z")

    def test_convert_to_response_format_empty(self):
        """Test response format conversion for empty result"""
        result = self.message_processor._convert_to_response_format({})
        self.assertEqual(result, {})

    def test_convert_to_response_format_with_code(self):
        """Test response format conversion for result with code"""
        test_result = {"code": 0, "msg": "success"}
        result = self.message_processor._convert_to_response_format(test_result)
        self.assertEqual(result, test_result)

    def test_convert_to_response_format_with_action(self):
        """Test response format conversion for card action result"""
        test_result = {
            "action": {"type": "update", "card": {}},
            "immediate": True
        }
        result = self.message_processor._convert_to_response_format(test_result)
        self.assertEqual(result["action"], test_result["action"])
        self.assertEqual(result["immediate"], True)

    def test_convert_to_response_format_default_success(self):
        """Test response format conversion for unknown result format"""
        test_result = {"ok": True, "some_field": "value"}
        result = self.message_processor._convert_to_response_format(test_result)
        self.assertEqual(result["code"], 0)
        self.assertEqual(result["msg"], "success")

    @patch('src.feishu_websocket.OpenCodeEventProcessor._convert_to_webhook_format')
    @patch('src.feishu_websocket.threading.Thread')
    @patch('src.feishu_websocket.asyncio')
    def test_do_method_success(self, mock_asyncio, mock_thread, mock_convert):
        """Test do() method with successful processing"""
        # Mock the conversion
        mock_convert.return_value = {"schema": "2.0", "header": {"event_type": "im.message.receive_v1"}}
        
        # Mock the async processing
        mock_loop = MagicMock()
        mock_loop.run_until_complete.return_value = {"ok": True, "session_id": "test_session"}
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_asyncio.set_event_loop = MagicMock()
        
        # Mock the background tasks
        mock_background_tasks = MagicMock()
        mock_background_tasks.run_all = AsyncMock()
        
        # We need to mock the import inside do() method
        with patch('src.feishu_websocket.MockBackgroundTasks', return_value=mock_background_tasks):
            with patch('src.feishu_websocket.OpenCodeEventProcessor._convert_to_response_format') as mock_convert_response:
                mock_convert_response.return_value = {"code": 0, "msg": "success"}
                
                # Call do() method
                result = self.message_processor.do(self.sample_sdk_v2_event)
                
                # Verify
                mock_convert.assert_called_once_with(self.sample_sdk_v2_event)
                mock_thread.assert_called_once()
                self.assertEqual(result, {"code": 0, "msg": "success"})

    def test_do_method_timeout(self):
        """Test do() method with timeout (should return success to prevent retry)"""
        # We'll test this by mocking the Future to timeout
        from concurrent.futures import Future
        
        # Create a mock future that times out
        mock_future = Future()
        
        with patch('src.feishu_websocket.OpenCodeEventProcessor._convert_to_webhook_format') as mock_convert:
            with patch('src.feishu_websocket.threading.Thread') as mock_thread:
                with patch('src.feishu_websocket.Future', return_value=mock_future):
                    # Mock the result method to raise TimeoutError
                    mock_future.result = MagicMock(side_effect=TimeoutError)
                    
                    # Call do() method
                    result = self.message_processor.do(self.sample_sdk_v2_event)
                    
                    # Should return success even on timeout
                    self.assertEqual(result["code"], 0)
                    self.assertEqual(result["msg"], "success")
                    self.assertEqual(result["note"], "processing_in_background")

    def test_do_method_exception(self):
        """Test do() method with exception (should return success to prevent retry)"""
        with patch('src.feishu_websocket.OpenCodeEventProcessor._convert_to_webhook_format') as mock_convert:
            mock_convert.side_effect = Exception("Test exception")
            
            # Call do() method
            result = self.message_processor.do(self.sample_sdk_v2_event)
            
            # Should return success even on exception
            self.assertEqual(result["code"], 500)
            self.assertIn("处理失败", result["msg"])


class TestEventFormatCompatibility(unittest.TestCase):
    """Test event format compatibility between SDK and webhook"""
    
    def test_realistic_event_samples(self):
        """Test with realistic event samples"""
        # Sample from Feishu documentation
        realistic_v2_event = {
            "schema": "2.0",
            "header": {
                "event_id": "f5f0b3c5e6c14d1c9b67e2a5d8c3b3a5",
                "event_type": "im.message.receive_v1",
                "create_time": "2023-03-23T11:30:50+08:00",
                "token": "verification_token",
                "app_id": "cli_xxx",
                "tenant_key": "xxx"
            },
            "event": {
                "sender": {
                    "sender_id": {
                        "union_id": "on_xxx",
                        "user_id": "xxx",
                        "open_id": "ou_xxx"
                    },
                    "sender_type": "user",
                    "tenant_key": "xxx"
                },
                "message": {
                    "message_id": "om_xxx",
                    "root_id": "om_xxx",
                    "parent_id": "om_xxx",
                    "create_time": "1608880752000000",
                    "chat_id": "oc_xxx",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": '{"text":"@_user_1 hello"}',
                    "mentions": [
                        {
                            "key": "@_user_1",
                            "id": {
                                "union_id": "on_xxx",
                                "user_id": "xxx",
                                "open_id": "ou_xxx"
                            },
                            "name": "Tom",
                            "tenant_key": "xxx"
                        }
                    ]
                }
            }
        }
        
        processor = OpenCodeEventProcessor("im.message.receive_v1")
        result = processor._convert_to_webhook_format(realistic_v2_event)
        
        # Should be unchanged for v2
        self.assertEqual(result["schema"], "2.0")
        self.assertEqual(result["header"]["event_type"], "im.message.receive_v1")
        self.assertEqual(result["event"]["message"]["chat_id"], "oc_xxx")
        
    def test_card_event_format(self):
        """Test card action event format"""
        card_event = {
            "schema": "2.0",
            "header": {
                "event_id": "xxx",
                "event_type": "card.action.trigger",
                "token": "verification_token",
                "create_time": "2023-03-23T11:30:50+08:00",
                "app_id": "cli_xxx",
                "tenant_key": "xxx"
            },
            "event": {
                "open_id": "ou_xxx",
                "user_id": "xxx",
                "open_message_id": "om_xxx",
                "open_chat_id": "oc_xxx",
                "tenant_key": "xxx",
                "action": {
                    "tag": "button",
                    "value": "{\"key\":\"value\"}"
                },
                "operator": {
                    "open_id": "ou_xxx"
                }
            }
        }
        
        processor = OpenCodeEventProcessor("card.action.trigger")
        result = processor._convert_to_webhook_format(card_event)
        
        self.assertEqual(result["schema"], "2.0")
        self.assertEqual(result["header"]["event_type"], "card.action.trigger")
        self.assertEqual(result["event"]["action"]["tag"], "button")


if __name__ == "__main__":
    unittest.main()