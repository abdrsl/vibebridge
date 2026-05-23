from pathlib import Path
from typing import Optional, Union

from .feishu_client import feishu_client
from .temp_file_manager import temp_file_manager


class FileSender:
    """文件发送器，用于发送临时文件到飞书"""

    def __init__(self, feishu_client_instance=None):
        self.feishu_client = feishu_client_instance or feishu_client

    async def send_file_to_feishu(
        self,
        file_path: Union[str, Path],
        receive_id: Optional[str] = None,
        file_name: Optional[str] = None,
        delete_after_send: bool = True,
    ) -> dict:
        """
        发送文件到飞书

        Args:
            file_path: 文件路径
            receive_id: 飞书群聊ID（可选，使用默认配置）
            file_name: 自定义文件名（可选）
            delete_after_send: 发送后是否删除临时文件

        Returns:
            发送结果
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            # 发送文件
            result = await self.feishu_client.send_file_from_path(
                receive_id=receive_id,
                file_path=path,
                file_name=file_name,
            )

            # 发送后清理
            if delete_after_send and path.parent == temp_file_manager.base_dir:
                temp_file_manager.delete_file(path)

            return {
                "success": True,
                "result": result,
                "file_path": str(path),
                "file_name": path.name,
            }

        except Exception as e:
            return {
                "error": f"Failed to send file: {str(e)}",
                "file_path": str(path),
            }

    async def send_text_as_file(
        self,
        text: str,
        filename: str = "output.txt",
        receive_id: Optional[str] = None,
        delete_after_send: bool = True,
    ) -> dict:
        """
        将文本内容作为文件发送到飞书

        Args:
            text: 文本内容
            filename: 文件名
            receive_id: 飞书群聊ID
            delete_after_send: 发送后是否删除临时文件

        Returns:
            发送结果
        """
        # 确保文件名有扩展名
        if not Path(filename).suffix:
            filename = f"{filename}.txt"

        # 创建临时文件
        temp_file = temp_file_manager.create_temp_file(
            content=text, extension=Path(filename).suffix, prefix="send_"
        )

        # 发送文件
        return await self.send_file_to_feishu(
            file_path=temp_file,
            receive_id=receive_id,
            file_name=filename,
            delete_after_send=delete_after_send,
        )

    async def send_html_as_file(
        self,
        html_content: str,
        filename: str = "output.html",
        receive_id: Optional[str] = None,
        delete_after_send: bool = True,
    ) -> dict:
        """
        将HTML内容作为文件发送到飞书

        Args:
            html_content: HTML内容
            filename: 文件名（确保是.html扩展名）
            receive_id: 飞书群聊ID
            delete_after_send: 发送后是否删除临时文件

        Returns:
            发送结果
        """
        # 确保是HTML文件
        if not filename.endswith(".html"):
            filename = f"{filename}.html"

        return await self.send_text_as_file(
            text=html_content,
            filename=filename,
            receive_id=receive_id,
            delete_after_send=delete_after_send,
        )

    async def send_multiple_files(
        self,
        file_paths: list[Union[str, Path]],
        receive_id: Optional[str] = None,
        delete_after_send: bool = True,
    ) -> list[dict]:
        """
        批量发送多个文件到飞书

        Args:
            file_paths: 文件路径列表
            receive_id: 飞书群聊ID
            delete_after_send: 发送后是否删除临时文件

        Returns:
            发送结果列表
        """
        results = []
        for file_path in file_paths:
            result = await self.send_file_to_feishu(
                file_path=file_path,
                receive_id=receive_id,
                delete_after_send=delete_after_send,
            )
            results.append(result)

        return results


# 全局实例
file_sender = FileSender()


async def send_temp_file_to_feishu(
    content: str,
    extension: str = ".txt",
    filename: Optional[str] = None,
    receive_id: Optional[str] = None,
) -> dict:
    """
    快速发送临时文件到飞书（简化接口）

    Args:
        content: 文件内容
        extension: 文件扩展名
        filename: 文件名（可选）
        receive_id: 飞书群聊ID（可选）

    Returns:
        发送结果
    """
    if not filename:
        filename = f"file{extension}"

    return await file_sender.send_text_as_file(
        text=content,
        filename=filename,
        receive_id=receive_id,
        delete_after_send=True,
    )


async def send_html_to_feishu(
    html_content: str,
    filename: str = "output.html",
    receive_id: Optional[str] = None,
) -> dict:
    """
    快速发送HTML文件到飞书

    Args:
        html_content: HTML内容
        filename: 文件名
        receive_id: 飞书群聊ID

    Returns:
        发送结果
    """
    return await file_sender.send_html_as_file(
        html_content=html_content,
        filename=filename,
        receive_id=receive_id,
        delete_after_send=True,
    )
