#!/usr/bin/env python3
"""
Feishu WebSocket 长连接客户端
基于飞书官方 SDK (lark-oapi) 的事件订阅2.0长连接模式
参考文档：https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-/event-subscription-2-0
"""

import asyncio
import json
import logging
import os
import random
import threading
import time
from typing import Any, Callable, List, Optional

# 飞书 SDK 导入
from lark_oapi.event.dispatcher_handler import (
    EventDispatcherHandler,
    ICallBackProcessor,
)

# 配置管理器
try:
    from .legacy.config_manager import get_config_manager

    config_manager = get_config_manager()
except ImportError:
    # 回退到环境变量
    config_manager = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 全局 WebSocket 客户端实例
_active_websocket_client: Optional["FeishuWebSocketClient"] = None
_active_websocket_lock = threading.Lock()


def get_websocket_client() -> Optional["FeishuWebSocketClient"]:
    """获取当前活动的 WebSocket 客户端实例"""
    with _active_websocket_lock:
        return _active_websocket_client


def set_websocket_client(client: Optional["FeishuWebSocketClient"]) -> None:
    """设置当前活动的 WebSocket 客户端实例"""
    global _active_websocket_client
    with _active_websocket_lock:
        _active_websocket_client = client


async def stop_websocket_client() -> bool:
    """停止当前活动的 WebSocket 客户端"""
    client = get_websocket_client()
    if client:
        try:
            logger.info("正在停止 WebSocket 客户端...")
            await client.stop()
            set_websocket_client(None)
            logger.info("WebSocket 客户端已停止")
            return True
        except Exception as e:
            logger.error(f"停止 WebSocket 客户端失败: {e}")
            return False
    else:
        logger.info("没有活动的 WebSocket 客户端")
        return True


async def restart_websocket_client() -> bool:
    """重启 WebSocket 客户端（根据当前配置）"""
    # 先停止现有客户端
    await stop_websocket_client()

    # 检查配置是否启用 WebSocket
    if config_manager:
        enabled = config_manager.is_websocket_enabled()
    else:
        # 回退到环境变量
        enabled = os.getenv("FEISHU_WEBSOCKET_ENABLED", "false").lower() == "true"

    if enabled:
        logger.info("配置启用 WebSocket，正在启动...")
        client = await start_feishu_websocket()
        if client:
            set_websocket_client(client)
            return True
        else:
            logger.error("WebSocket 客户端启动失败")
            return False
    else:
        logger.info("配置禁用 WebSocket，保持停止状态")
        return True


class MockBackgroundTasks:
    """模拟 FastAPI 的 BackgroundTasks 类，用于兼容现有处理器"""

    def __init__(self):
        # 延迟导入，避免 asyncio 初始化问题
        self.tasks: List[tuple] = []

    def add_task(self, func: Callable, *args, **kwargs):
        """添加后台任务"""
        self.tasks.append((func, args, kwargs))

    async def run_all(self):
        """运行所有后台任务"""
        import asyncio

        # BackgroundTasks 本身会在响应返回后自动执行任务
        # 但在这里我们需要手动执行
        for func, args, kwargs in self.tasks:
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    # 如果是同步函数，在异步上下文中运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, func, *args, **kwargs)
            except Exception as e:
                logger.error(f"后台任务执行失败: {e}")


class OpenCodeEventProcessor:
    """OpenCode-Feishu Bridge 事件处理器

    将飞书事件转换为现有 webhook 格式并调用 process_feishu_webhook
    """

    def __init__(self, event_type: str):
        self._event_type = event_type

    def type(self):
        """返回事件数据类型

        注意：这里返回 dict 类型，因为我们需要原始的事件数据
        实际处理时会根据事件类型动态解析
        """
        return dict

    def do(self, data: dict) -> Any:
        """处理事件

        Args:
            data: 飞书事件数据（已解析的字典）

        Returns:
            处理结果，将返回给飞书服务器
        """
        try:
            logger.info(f"处理飞书事件: {self._event_type}")
            logger.debug(
                f"收到原始事件数据: {json.dumps(data, ensure_ascii=False)[:500]}"
            )

            # 将 SDK 事件格式转换为现有 webhook 格式
            webhook_body = self._convert_to_webhook_format(data)
            logger.debug(
                f"转换后的 webhook 格式: {json.dumps(webhook_body, ensure_ascii=False)[:500]}"
            )

            # 创建模拟的后台任务管理器
            background_tasks = MockBackgroundTasks()

            # 在单独的线程中运行异步处理，避免阻塞 WebSocket 客户端线程的事件循环
            import asyncio
            import threading
            from concurrent.futures import Future

            # 创建 Future 用于获取结果
            result_future = Future()

            def run_async_in_thread():
                """在单独线程中运行异步代码"""
                try:
                    # 在这个线程中创建新的事件循环
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # 延迟导入，避免 asyncio 初始化问题
                    from .legacy.feishu_card_handler import process_feishu_webhook

                    # 运行异步处理
                    result = loop.run_until_complete(
                        process_feishu_webhook(webhook_body, background_tasks)
                    )

                    # 运行后台任务
                    loop.run_until_complete(background_tasks.run_all())

                    # 设置结果
                    result_future.set_result(result)

                except Exception as e:
                    result_future.set_exception(e)
                finally:
                    # 清理事件循环
                    if loop and not loop.is_closed():
                        loop.close()

            # 启动线程运行异步处理
            thread = threading.Thread(target=run_async_in_thread, daemon=True)
            thread.start()

            # 等待结果（最多 10 秒）
            try:
                result = result_future.result(timeout=10.0)
                logger.debug(f"事件处理完成，结果: {result}")

                # 返回处理结果（将发送回飞书服务器）
                return self._convert_to_response_format(result)

            except TimeoutError:
                # 超时，但事件会在后台继续处理
                logger.warning("事件处理超时（10秒），但会在后台继续处理")
                # 返回成功响应，避免飞书重试
                return {"code": 0, "msg": "success", "note": "processing_in_background"}
            except Exception as e:
                logger.error(f"等待事件处理结果出错: {e}")
                # 其他错误也返回成功，避免飞书重试
                logger.warning(f"事件处理出错，但返回成功避免重试: {e}")
                return {"code": 0, "msg": "success", "note": "error_ignored"}

        except Exception as e:
            logger.error(f"处理飞书事件失败: {e}", exc_info=True)
            # 返回错误响应
            return {"code": 500, "msg": f"处理失败: {str(e)}"}

    def _convert_to_webhook_format(self, sdk_event: dict) -> dict:
        """将 SDK 事件格式转换为现有 webhook 格式

        SDK 事件格式与 webhook 格式类似，但可能有细微差别。
        这里根据实际事件类型进行转换。
        """
        # 检查是否是 v2 格式（schema 2.0）
        if "schema" in sdk_event and sdk_event["schema"] == "2.0":
            # 已经是 v2 格式，直接返回
            return sdk_event

        # 检查是否是 v1 格式（有 uuid 字段）
        if "uuid" in sdk_event:
            # v1 格式，转换为统一格式
            return {
                "schema": "1.0",
                "header": {
                    "event_id": sdk_event.get("event_id", ""),
                    "event_type": sdk_event.get("event", {}).get("type", ""),
                    "create_time": sdk_event.get("ts", ""),
                    "token": sdk_event.get("token", ""),
                    "app_id": sdk_event.get("app_id", ""),
                    "tenant_key": sdk_event.get("tenant_key", ""),
                },
                "event": sdk_event.get("event", {}),
            }

        # 未知格式，尝试直接使用
        logger.warning(
            f"未知的事件格式: {json.dumps(sdk_event, ensure_ascii=False)[:200]}..."
        )
        return sdk_event

    def _convert_to_response_format(self, webhook_result: dict) -> dict:
        """将 webhook 处理结果转换为 SDK 响应格式"""
        # 默认返回空字典表示成功
        if not webhook_result:
            return {}

        # 如果已经有特定的响应格式，直接返回
        if "code" in webhook_result or "msg" in webhook_result:
            return webhook_result

        # 对于卡片动作响应，需要特定格式
        if "action" in webhook_result:
            # 卡片动作响应
            return {
                "action": webhook_result.get("action", {}),
                "immediate": webhook_result.get("immediate", True),
            }

        # 默认成功响应
        return {"code": 0, "msg": "success"}


class OpenCodeEventHandler(EventDispatcherHandler):
    """OpenCode-Feishu Bridge 事件分发处理器

    注册所有需要处理的事件类型
    """

    def __init__(self):
        super().__init__()

        # 注册需要处理的事件类型
        self._register_processors()

    def on_open(self, *args, **kwargs):
        """WebSocket 连接建立时调用"""
        logger.info(f"WebSocket 连接已建立，参数: args={args}, kwargs={kwargs}")
        super().on_open(*args, **kwargs)

    def on_close(self, *args, **kwargs):
        """WebSocket 连接关闭时调用"""
        logger.info(f"WebSocket 连接已关闭，参数: args={args}, kwargs={kwargs}")
        super().on_close(*args, **kwargs)

    def on_error(self, *args, **kwargs):
        """WebSocket 连接出错时调用"""
        logger.error(f"WebSocket 连接错误，参数: args={args}, kwargs={kwargs}")
        super().on_error(*args, **kwargs)

    def on_message(self, *args, **kwargs):
        """收到 WebSocket 消息时调用"""
        logger.debug(f"收到 WebSocket 消息，参数: args={args}, kwargs={kwargs}")
        super().on_message(*args, **kwargs)

    def _register_processors(self):
        """注册事件处理器"""

        # IM 消息接收事件
        self.register_callback_processor(
            "p2.im.message.receive_v1", OpenCodeEventProcessor("im.message.receive_v1")
        )

        # 卡片动作触发事件
        self.register_callback_processor(
            "p2.card.action.trigger", OpenCodeEventProcessor("card.action.trigger")
        )

        # 其他可能需要的事件类型可以在这里添加
        # self.register_callback_processor("p2.im.chat.member.bot.added_v1", ...)
        # self.register_callback_processor("p2.im.chat.member.bot.deleted_v1", ...)

    def register_callback_processor(
        self, event_key: str, processor: ICallBackProcessor
    ):
        """注册回调处理器"""
        self._callback_processor_map[event_key] = processor
        logger.info(f"注册事件处理器: {event_key}")


class FeishuWebSocketClient:
    """Feishu WebSocket 长连接客户端（基于官方 SDK）"""

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")

        if not self.app_id or not self.app_secret:
            logger.error("FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置")
            raise ValueError("Feishu 应用配置不完整")

        # 创建事件处理器
        self.event_handler = OpenCodeEventHandler()

        # 注意：不在 __init__ 中创建 Client 实例，因为需要在后台线程中创建
        # 每个线程需要自己的 Client 实例和事件循环
        self.running = False
        self._client_thread: Optional[threading.Thread] = None
        self._client: Optional["Client"] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """启动 WebSocket 客户端（在后台线程中运行）"""
        if self.running:
            logger.warning("WebSocket 客户端已经在运行")
            return

        logger.info("启动 Feishu WebSocket 客户端...")

        # 在后台线程中运行客户端
        def run_client():
            thread_id = threading.get_ident()
            logger.info(f"WebSocket 客户端线程启动 (线程ID: {thread_id})")

            # 在这个线程中重新导入需要的模块，避免线程间状态污染
            import asyncio
            import logging

            # 创建新的事件循环并设置为当前线程的事件循环
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            # 修改 SDK 模块中的全局 loop 变量
            from lark_oapi import ws

            ws.client.loop = new_loop
            # 保存循环引用以便停止时使用
            self._client_loop = new_loop
            from lark_oapi.core.enum import LogLevel
            from lark_oapi.ws import Client

            # 配置 SDK 日志（在这个线程中）
            sdk_logger = logging.getLogger("lark_oapi")
            sdk_logger.setLevel(logging.DEBUG)
            # 确保有处理器
            if not sdk_logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                )
                sdk_logger.addHandler(handler)

            app_id = self.app_id
            app_secret = self.app_secret
            event_handler = self.event_handler

            logger.debug(f"线程 {thread_id}: running={self.running}")

            # 重试计数和退避配置
            retry_count = 0
            max_retry_delay = 300  # 5 minutes
            base_delay = 5

            while self.running:
                try:
                    logger.debug(f"线程 {thread_id}: 创建 WebSocket 客户端")
                    start_time = time.time()

                    # 创建客户端实例
                    client = Client(
                        app_id=app_id,
                        app_secret=app_secret,
                        event_handler=event_handler,
                        auto_reconnect=True,
                        log_level=LogLevel.DEBUG,
                    )

                    # 保存 client 引用以便停止
                    self._client = client

                    logger.info(f"线程 {thread_id}: 开始运行 WebSocket 客户端")
                    client.start()
                    logger.info(f"线程 {thread_id}: WebSocket 客户端退出")

                    # 计算连接持续时间
                    duration = time.time() - start_time
                    if duration > 30:  # 连接稳定超过30秒，重置重试计数
                        retry_count = 0
                        logger.info(
                            f"线程 {thread_id}: 连接稳定 {duration:.1f} 秒，重置重试计数"
                        )
                    else:
                        retry_count += 1
                        logger.warning(
                            f"线程 {thread_id}: 连接不稳定，仅持续 {duration:.1f} 秒，重试计数: {retry_count}"
                        )

                except Exception as e:
                    logger.error(
                        f"线程 {thread_id}: WebSocket 客户端运行失败: {e}",
                        exc_info=True,
                    )
                    retry_count += 1
                    logger.warning(
                        f"线程 {thread_id}: 异常失败，重试计数: {retry_count}"
                    )

                # 如果仍在运行，则等待后重试
                if self.running:
                    # 指数退避 + 抖动
                    delay = min(
                        base_delay * (2 ** min(retry_count, 10)), max_retry_delay
                    )
                    jitter = random.uniform(0.8, 1.2)  # ±20% 抖动
                    actual_delay = delay * jitter
                    logger.info(
                        f"线程 {thread_id}: {actual_delay:.1f} 秒后重试 (重试计数: {retry_count})"
                    )
                    time.sleep(actual_delay)
                else:
                    break

            logger.info(f"线程 {thread_id}: 退出")

        self.running = True
        self._client_thread = threading.Thread(target=run_client, daemon=True)
        self._client_thread.start()

        logger.info("Feishu WebSocket 客户端已启动")

    async def stop(self):
        """停止 WebSocket 客户端"""
        if not self.running:
            return

        logger.info("停止 Feishu WebSocket 客户端...")

        # 注意：lark_oapi.ws.Client 没有提供直接的 stop 方法
        # 这里通过设置 running 标志，让客户端在下次重连时停止
        self.running = False

        # 尝试通过反射调用内部断开连接方法
        # 如果存在客户端循环，在客户端循环中执行关闭操作
        if self._client_loop and self._client_loop.is_running():
            try:
                # 在客户端循环中安排关闭任务
                future = asyncio.run_coroutine_threadsafe(
                    self._close_connection(), self._client_loop
                )
                # 等待最多 2 秒
                future.result(timeout=2.0)
                logger.debug("已在客户端循环中关闭连接")
            except Exception as e:
                logger.debug(f"在客户端循环中关闭连接时出错: {e}")
        else:
            # 备用方案：直接尝试关闭连接（可能在不同的事件循环中）
            try:
                if (
                    self._client
                    and hasattr(self._client, "_conn")
                    and self._client._conn
                ):
                    # 关闭 WebSocket 连接
                    await self._client._conn.close()
                    logger.debug("已关闭 WebSocket 连接")
            except Exception as e:
                logger.debug(f"关闭连接时出错（可能已断开）: {e}")

        # 无法直接停止客户端线程，但可以等待线程结束
        if self._client_thread and self._client_thread.is_alive():
            logger.info("等待 WebSocket 客户端线程结束...")
            # 客户端线程会在连接断开后自动结束
            # 这里等待一小段时间，但不阻塞主事件循环
            for _ in range(10):  # 等待最多 1 秒
                if not self._client_thread.is_alive():
                    break
                await asyncio.sleep(0.1)

        logger.info("Feishu WebSocket 客户端已停止")

    async def _close_connection(self):
        """在客户端循环中关闭 WebSocket 连接"""
        try:
            if self._client and hasattr(self._client, "_conn") and self._client._conn:
                await self._client._conn.close()
                logger.debug("已在客户端循环中关闭 WebSocket 连接")
        except Exception as e:
            logger.debug(f"在客户端循环中关闭连接时出错: {e}")


async def start_feishu_websocket():
    """启动 Feishu WebSocket 客户端（如果启用）"""
    # 检查是否启用 WebSocket（优先使用配置管理器）
    if config_manager:
        enabled = config_manager.is_websocket_enabled()
    else:
        # 回退到环境变量
        enabled = os.getenv("FEISHU_WEBSOCKET_ENABLED", "false").lower() == "true"

    if not enabled:
        logger.info("Feishu WebSocket 未启用（根据配置）")
        return None

    # 检查配置是否完整
    if not os.getenv("FEISHU_APP_ID") or not os.getenv("FEISHU_APP_SECRET"):
        logger.error("FEISHU_APP_ID 或 FEISHU_APP_SECRET 未配置，无法启动 WebSocket")
        return None

    # 配置 SDK 日志记录
    import logging

    sdk_logger = logging.getLogger("lark_oapi")
    sdk_logger.setLevel(logging.DEBUG)

    # 添加控制台处理器
    if not sdk_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        sdk_logger.addHandler(handler)

    try:
        logger.info("创建 FeishuWebSocketClient 实例...")
        client = FeishuWebSocketClient()
        logger.info("启动 FeishuWebSocketClient...")
        await client.start()
        logger.info("Feishu WebSocket 客户端启动成功")
        # 保存客户端实例到全局变量
        set_websocket_client(client)
        return client
    except Exception as e:
        logger.error(f"启动 Feishu WebSocket 客户端失败: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # 测试 WebSocket 客户端

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 从环境变量加载配置
    from dotenv import load_dotenv

    load_dotenv()

    async def test():
        client = await start_feishu_websocket()
        if client:
            print("✅ WebSocket 客户端已启动")
            print("按 Ctrl+C 停止...")

            # 保持运行
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n停止客户端...")
                await client.stop()
        else:
            print("❌ WebSocket 客户端启动失败")

    asyncio.run(test())
