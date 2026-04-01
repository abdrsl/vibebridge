"""
简单技能管理器 - 用于集成文件发送等简单技能
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from .file_sender import send_html_to_feishu, send_temp_file_to_feishu
from .temp_file_manager import temp_file_manager


class SimpleSkillManager:
    """简单技能管理器"""

    def __init__(self):
        self.skills = {}
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """注册内置技能"""
        self.register_skill("send_file", self._send_file_skill)
        self.register_skill("send_html", self._send_html_skill)
        self.register_skill("create_temp_file", self._create_temp_file_skill)
        self.register_skill("list_temp_files", self._list_temp_files_skill)

    def register_skill(self, name: str, handler):
        """注册技能"""
        self.skills[name] = handler

    def execute_skill(self, skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        if skill_name not in self.skills:
            return {"error": f"Skill not found: {skill_name}"}

        try:
            return self.skills[skill_name](params)
        except Exception as e:
            return {"error": f"Skill execution failed: {str(e)}"}

    def _send_file_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送文件技能"""
        content = params.get("content")
        filename = params.get("filename", "output.txt")
        receive_id = params.get("receive_id")
        file_type = params.get("file_type", "text")

        if not content:
            return {"error": "Missing content parameter"}

        # 根据文件类型调整文件名
        if file_type == "html" and not filename.endswith(".html"):
            filename = f"{filename}.html"
        elif file_type == "json" and not filename.endswith(".json"):
            filename = f"{filename}.json"

        # 同步调用异步函数
        try:
            # 获取当前事件循环或创建新的事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if file_type == "html":
                result = loop.run_until_complete(
                    send_html_to_feishu(
                        html_content=content,
                        filename=filename,
                        receive_id=receive_id,
                    )
                )
            else:
                result = loop.run_until_complete(
                    send_temp_file_to_feishu(
                        content=content,
                        extension=Path(filename).suffix,
                        filename=filename,
                        receive_id=receive_id,
                    )
                )

            if "error" in result:
                return {"error": f"Failed to send file: {result.get('error')}"}

            return {
                "success": True,
                "message": f"File '{filename}' sent to Feishu",
                "file_size": len(content),
                "result": result,
            }

        except Exception as e:
            return {"error": f"Failed to send file: {str(e)}"}

    def _send_html_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送HTML文件技能（send_file的快捷方式）"""
        params["file_type"] = "html"
        if "filename" not in params:
            params["filename"] = "output.html"
        return self._send_file_skill(params)

    def _create_temp_file_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """创建临时文件技能"""
        content = params.get("content", "")
        extension = params.get("extension", ".txt")
        prefix = params.get("prefix", "temp_")

        try:
            filepath = temp_file_manager.create_temp_file(
                content=content, extension=extension, prefix=prefix
            )

            file_info = temp_file_manager.get_file_info(filepath)

            return {
                "success": True,
                "message": f"Temporary file created: {filepath.name}",
                "file_info": file_info,
                "file_path": str(filepath),
            }

        except Exception as e:
            return {"error": f"Failed to create temp file: {str(e)}"}

    def _list_temp_files_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出临时文件技能"""
        pattern = params.get("pattern", "*")

        try:
            files = temp_file_manager.list_files(pattern)

            return {
                "success": True,
                "count": len(files),
                "files": files,
            }

        except Exception as e:
            return {"error": f"Failed to list files: {str(e)}"}

    def check_constitution(self, user_input: str) -> Dict[str, Any]:
        """
        简单的宪法检查（兼容接口）

        Args:
            user_input: 用户输入

        Returns:
            检查结果
        """
        # 简单的安全检查
        dangerous_keywords = [
            "hack",
            "入侵",
            "攻击",
            "病毒",
            "恶意软件",
            "exploit",
            "bypass",
            "绕过",
            "crack",
            "破解",
            "steal",
            "窃取",
        ]

        violations = []
        warnings = []

        user_input_lower = user_input.lower()

        for keyword in dangerous_keywords:
            if keyword in user_input_lower:
                warnings.append(
                    {
                        "message": f"输入包含潜在危险关键词: {keyword}",
                        "severity": "warning",
                    }
                )

        return {
            "has_violations": False,
            "has_warnings": len(warnings) > 0,
            "violations": violations,
            "warnings": warnings,
            "suggested_action": "proceed" if len(warnings) == 0 else "review",
        }

    def generate_session_name(self, user_input: str) -> str:
        """
        生成会话名称（兼容接口）

        Args:
            user_input: 用户输入

        Returns:
            会话名称
        """
        # 简单的会话名称生成
        import hashlib
        import time

        # 取前30个字符作为基础
        base_name = user_input[:30].strip()
        if not base_name:
            base_name = "task"

        # 添加时间戳和哈希
        timestamp = time.strftime("%H%M%S")
        hash_str = hashlib.md5(user_input.encode()).hexdigest()[:6]

        return f"{base_name}_{timestamp}_{hash_str}"


# 全局实例
_simple_skill_manager: Optional[SimpleSkillManager] = None


def get_simple_skill_manager() -> SimpleSkillManager:
    """获取简单技能管理器实例"""
    global _simple_skill_manager

    if _simple_skill_manager is None:
        _simple_skill_manager = SimpleSkillManager()

    return _simple_skill_manager


# 兼容性函数
def check_constitution(user_input: str) -> Dict[str, Any]:
    """宪法检查（兼容接口）"""
    manager = get_simple_skill_manager()
    return manager.check_constitution(user_input)


def generate_session_name(user_input: str) -> str:
    """生成会话名称（兼容接口）"""
    manager = get_simple_skill_manager()
    return manager.generate_session_name(user_input)


def execute_skill(skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行技能（兼容接口）"""
    manager = get_simple_skill_manager()
    return manager.execute_skill(skill_name, params)


if __name__ == "__main__":
    # 测试技能管理器
    manager = get_simple_skill_manager()

    print("简单技能管理器测试")
    print("=" * 60)

    # 测试宪法检查
    test_input = "请帮我创建一个HTML页面"
    print(f"\n宪法检查测试: {test_input}")
    result = manager.check_constitution(test_input)
    print(f"  是否有违规: {result['has_violations']}")
    print(f"  是否有警告: {result['has_warnings']}")

    # 测试会话名称生成
    session_name = manager.generate_session_name(test_input)
    print(f"  生成的会话名称: {session_name}")

    # 测试技能执行
    print("\n技能执行测试:")

    # 创建临时文件
    print("\n1. 创建临时文件:")
    result = manager.execute_skill(
        "create_temp_file",
        {"content": "测试内容", "extension": ".txt", "prefix": "test_"},
    )
    print(f"   结果: {result}")

    # 列出临时文件
    print("\n2. 列出临时文件:")
    result = manager.execute_skill("list_temp_files", {})
    print(f"   文件数量: {result.get('count', 0)}")

    print("\n" + "=" * 60)
    print("测试完成")
