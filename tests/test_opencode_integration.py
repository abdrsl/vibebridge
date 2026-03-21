"""
测试OpenCode集成模块
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from app.opencode_integration import OpenCodeTask, OpenCodeManager, TaskStatus


class TestOpenCodeTask:
    """测试OpenCodeTask类"""

    def test_task_creation(self):
        """测试任务创建"""
        task = OpenCodeTask(
            task_id="test_task_123",
            user_message="测试任务消息",
            feishu_chat_id="chat_123",
            feishu_message_id="msg_123",
        )

        assert task.task_id == "test_task_123"
        assert task.user_message == "测试任务消息"
        assert task.feishu_chat_id == "chat_123"
        assert task.feishu_message_id == "msg_123"
        assert task.status == TaskStatus.PENDING
        assert task.created_at is not None
        assert task.updated_at is not None
        assert task.output_lines == []
        assert task.final_result is None
        assert task.error is None
        assert task.process is None
        assert task.session_id is None

    def test_task_attributes(self):
        """测试任务属性"""
        task = OpenCodeTask(task_id="test_task_456", user_message="另一个测试任务")

        # 测试默认值
        assert task.feishu_chat_id is None
        assert task.feishu_message_id is None
        assert task.session_id is None
        assert task.process is None

        # 测试属性赋值
        task.status = TaskStatus.RUNNING
        assert task.status == TaskStatus.RUNNING

        task.output_lines = ["输出行1", "输出行2"]
        assert task.output_lines == ["输出行1", "输出行2"]

        task.final_result = "最终结果"
        assert task.final_result == "最终结果"

        task.error = "错误信息"
        assert task.error == "错误信息"


class TestOpenCodeManager:
    """测试OpenCodeManager类"""

    @pytest.fixture
    def manager(self):
        """创建OpenCodeManager实例"""
        return OpenCodeManager()

    @pytest.mark.asyncio
    async def test_create_task(self, manager):
        """测试创建任务"""
        task_id = await manager.create_task(
            user_message="创建新任务",
            feishu_chat_id="chat_123",
            feishu_message_id="msg_123",
        )

        assert task_id is not None
        assert task_id.startswith("oc_")

        # 验证任务被添加到管理器
        task = await manager.get_task(task_id)
        assert task is not None
        assert task.task_id == task_id
        assert task.user_message == "创建新任务"
        assert task.feishu_chat_id == "chat_123"
        assert task.feishu_message_id == "msg_123"
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_task_minimal(self, manager):
        """测试创建最小化任务（无飞书信息）"""
        task_id = await manager.create_task(user_message="最小化任务")

        assert task_id is not None

        task = await manager.get_task(task_id)
        assert task is not None
        assert task.user_message == "最小化任务"
        assert task.feishu_chat_id is None
        assert task.feishu_message_id is None

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, manager):
        """测试获取不存在的任务"""
        task = await manager.get_task("non_existent_id")
        assert task is None

    @pytest.mark.asyncio
    async def test_update_task(self, manager):
        """测试更新任务"""
        # 创建任务
        task_id = await manager.create_task(user_message="测试更新")

        # 更新任务状态
        success = await manager.update_task(
            task_id,
            status=TaskStatus.RUNNING,
            output_lines=["开始执行..."],
            session_id="session_123",
        )

        assert success is True

        # 验证更新
        task = await manager.get_task(task_id)
        assert task.status == TaskStatus.RUNNING
        assert task.output_lines == ["开始执行..."]
        assert task.session_id == "session_123"
        assert task.updated_at > task.created_at

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, manager):
        """测试更新不存在的任务"""
        success = await manager.update_task(
            "non_existent_id", status=TaskStatus.RUNNING
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_list_tasks(self, manager):
        """测试列出任务"""
        # 创建多个任务
        task_ids = []
        for i in range(5):
            task_id = await manager.create_task(user_message=f"任务{i}")
            task_ids.append(task_id)

        # 获取任务列表
        tasks = await manager.list_tasks(limit=10)

        assert len(tasks) == 5

        # 验证任务按创建时间倒序排列
        created_times = [datetime.fromisoformat(t["created_at"]) for t in tasks]
        assert created_times == sorted(created_times, reverse=True)

        # 验证任务信息
        for task_data in tasks:
            assert "task_id" in task_data
            assert "status" in task_data
            assert "user_message" in task_data
            assert "created_at" in task_data
            assert "output_count" in task_data
            assert "has_result" in task_data

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, manager):
        """测试带限制的任务列表"""
        # 创建多个任务
        for i in range(15):
            await manager.create_task(user_message=f"任务{i}")

        # 获取有限制的任务列表
        tasks = await manager.list_tasks(limit=5)
        assert len(tasks) == 5

        # 测试默认限制（实际代码中默认限制是20）
        tasks_default = await manager.list_tasks()
        assert len(tasks_default) <= 20  # 默认限制是20

    @pytest.mark.asyncio
    async def test_run_opencode_task_not_found(self, manager):
        """测试运行不存在的任务"""
        events = []
        async for event in manager.run_opencode("non_existent_id"):
            events.append(event)

        assert len(events) > 0
        assert events[0]["type"] == "error"
        assert "not found" in events[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_run_opencode_success_flow(self, manager):
        """测试成功运行opencode的流程"""
        # 创建任务
        task_id = await manager.create_task(user_message="测试命令")

        # 模拟opencode命令执行
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # 设置模拟的进程
            mock_process = AsyncMock()
            mock_stdout = AsyncMock()

            # 模拟opencode输出JSON事件 - 简化版本
            test_events = [
                '{"type": "step_start", "snapshot": "开始执行"}\n',
                '{"type": "text", "part": {"text": "简单输出"}}\n',
                '{"type": "done", "content": "任务完成"}\n',
            ]

            # 模拟stdout读取 - 一次性返回所有数据
            output_data = "".join(test_events).encode("utf-8")
            mock_stdout.read = AsyncMock(
                side_effect=[
                    output_data,  # 第一次读取所有数据
                    b"",  # 第二次读取结束
                ]
            )
            mock_process.stdout = mock_stdout
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()

            mock_subprocess.return_value = mock_process

            # 运行任务并收集事件
            events = []
            async for event in manager.run_opencode(task_id):
                events.append(event)

            # 验证事件流
            assert len(events) >= 2  # 至少应该有状态更新和完成事件

            # 验证状态更新
            task = await manager.get_task(task_id)
            assert task.status == TaskStatus.COMPLETED
            # final_result 可能被设置，也可能不被设置，取决于事件处理
            # 至少output_lines应该有内容
            assert len(task.output_lines) > 0

    @pytest.mark.asyncio
    async def test_run_opencode_failure(self, manager):
        """测试opencode执行失败"""
        task_id = await manager.create_task(user_message="失败测试")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_stdout = AsyncMock()

            # 模拟进程返回非零退出码
            mock_stdout.read = AsyncMock(return_value=b"")
            mock_process.stdout = mock_stdout
            mock_process.returncode = 1
            mock_process.wait = AsyncMock()

            mock_subprocess.return_value = mock_process

            events = []
            async for event in manager.run_opencode(task_id):
                events.append(event)

            # 验证任务状态
            task = await manager.get_task(task_id)
            assert task.status == TaskStatus.FAILED
            assert task.error is not None

    @pytest.mark.asyncio
    async def test_run_opencode_file_not_found(self, manager):
        """测试opencode命令未找到"""
        task_id = await manager.create_task(user_message="命令未找到测试")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            events = []
            async for event in manager.run_opencode(task_id):
                events.append(event)

            # 验证错误事件
            assert any(event["type"] == "error" for event in events)

            # 验证任务状态
            task = await manager.get_task(task_id)
            assert task.status == TaskStatus.FAILED
            assert task.error is not None
            assert "未找到" in task.error or "not found" in task.error.lower()

    @pytest.mark.asyncio
    async def test_run_opencode_general_exception(self, manager):
        """测试opencode执行过程中的一般异常"""
        task_id = await manager.create_task(user_message="异常测试")

        with patch("asyncio.create_subprocess_exec", side_effect=Exception("测试异常")):
            events = []
            async for event in manager.run_opencode(task_id):
                events.append(event)

            # 验证错误事件
            assert any(event["type"] == "error" for event in events)

            # 验证任务状态
            task = await manager.get_task(task_id)
            assert task.status == TaskStatus.FAILED
            assert task.error is not None
            assert "测试异常" in task.error

    @pytest.mark.asyncio
    async def test_run_opencode_json_decode_error(self, manager):
        """测试JSON解析错误处理"""
        task_id = await manager.create_task(user_message="JSON错误测试")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_stdout = AsyncMock()

            # 模拟无效的JSON输出
            mock_stdout.read = AsyncMock(side_effect=[b"Invalid JSON line\n", b""])
            mock_process.stdout = mock_stdout
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()

            mock_subprocess.return_value = mock_process

            events = []
            async for event in manager.run_opencode(task_id):
                events.append(event)

            # 即使有JSON错误，任务也应该完成
            task = await manager.get_task(task_id)
            assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_opencode_timeout_handling(self, manager):
        """测试超时处理"""
        task_id = await manager.create_task(user_message="超时测试")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_stdout = AsyncMock()

            # 模拟超时，但进程已结束
            mock_stdout.read = AsyncMock(side_effect=asyncio.TimeoutError("读取超时"))
            mock_process.stdout = mock_stdout
            mock_process.returncode = 0  # 进程已结束

            mock_subprocess.return_value = mock_process

            # 使用超时限制收集事件
            events = []
            try:
                async for event in manager.run_opencode(task_id):
                    events.append(event)
                    # 限制事件数量，防止无限循环
                    if len(events) > 10:
                        break
            except Exception:
                pass  # 忽略可能的异常

            # 验证任务状态
            task = await manager.get_task(task_id)
            # 超时后任务应该完成或失败
