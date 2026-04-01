import mimetypes
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, Union

PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DIR = PROJECT_ROOT / "tmp"

# 确保临时目录存在
TEMP_DIR.mkdir(exist_ok=True)


class TempFileManager:
    """临时文件管理器，用于处理与项目无关的临时文件"""

    def __init__(self, base_dir: Path = TEMP_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(exist_ok=True)

    def create_temp_file(
        self, content: Union[str, bytes], extension: str = "", prefix: str = "temp_"
    ) -> Path:
        """
        创建临时文件

        Args:
            content: 文件内容，可以是字符串或字节
            extension: 文件扩展名（如 .html, .txt, .png）
            prefix: 文件名前缀

        Returns:
            临时文件的完整路径
        """
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{prefix}{timestamp}_{unique_id}{extension}"
        filepath = self.base_dir / filename

        # 写入内容
        if isinstance(content, str):
            filepath.write_text(content, encoding="utf-8")
        elif isinstance(content, bytes):
            filepath.write_bytes(content)
        else:
            raise ValueError("Content must be str or bytes")

        return filepath

    def save_uploaded_file(
        self, file: BinaryIO, filename: str, content_type: Optional[str] = None
    ) -> Path:
        """
        保存上传的文件到临时目录

        Args:
            file: 文件对象（如 FastAPI 的 UploadFile）
            filename: 原始文件名
            content_type: 文件类型（可选）

        Returns:
            保存后的文件路径
        """
        # 生成安全文件名
        safe_name = self._make_safe_filename(filename)
        filepath = self.base_dir / safe_name

        # 保存文件
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file, f)

        return filepath

    def get_file_info(self, filepath: Union[str, Path]) -> dict:
        """
        获取文件信息

        Args:
            filepath: 文件路径（相对或绝对）

        Returns:
            包含文件信息的字典
        """
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # 获取文件类型
        mime_type, _ = mimetypes.guess_type(str(path))

        return {
            "path": str(path),
            "name": path.name,
            "size": path.stat().st_size,
            "created": datetime.fromtimestamp(path.stat().st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            "mime_type": mime_type or "application/octet-stream",
            "extension": path.suffix.lower(),
            "is_text": self._is_text_file(path),
        }

    def read_file(
        self, filepath: Union[str, Path], as_text: bool = True
    ) -> Union[str, bytes]:
        """
        读取文件内容

        Args:
            filepath: 文件路径
            as_text: 是否以文本形式读取

        Returns:
            文件内容
        """
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if as_text:
            return path.read_text(encoding="utf-8")
        else:
            return path.read_bytes()

    def delete_file(self, filepath: Union[str, Path]) -> bool:
        """
        删除临时文件

        Args:
            filepath: 文件路径

        Returns:
            是否删除成功
        """
        path = Path(filepath)
        if not path.is_absolute():
            path = self.base_dir / path

        if path.exists():
            path.unlink()
            return True
        return False

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        清理超过指定时间的临时文件

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            删除的文件数量
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        for filepath in self.base_dir.iterdir():
            if filepath.is_file():
                if filepath.stat().st_mtime < cutoff_time:
                    filepath.unlink()
                    deleted_count += 1

        return deleted_count

    def list_files(self, pattern: str = "*") -> list[dict]:
        """
        列出临时目录中的文件

        Args:
            pattern: 文件匹配模式

        Returns:
            文件信息列表
        """
        files = []
        for filepath in self.base_dir.glob(pattern):
            if filepath.is_file():
                files.append(self.get_file_info(filepath))

        # 按修改时间排序（最新的在前）
        files.sort(key=lambda x: x["modified"], reverse=True)
        return files

    def _make_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除路径信息
        name = Path(filename).name

        # 替换不安全字符
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)

        # 确保文件名不为空
        if not safe_name.strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = f"file_{timestamp}"

        return safe_name

    def _is_text_file(self, filepath: Path) -> bool:
        """判断文件是否为文本文件"""
        text_extensions = {
            ".txt",
            ".html",
            ".htm",
            ".css",
            ".js",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".md",
            ".py",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".php",
            ".rb",
            ".pl",
            ".sh",
            ".bash",
            ".zsh",
            ".sql",
            ".csv",
            ".tsv",
            ".log",
        }

        # 通过扩展名判断
        if filepath.suffix.lower() in text_extensions:
            return True

        # 通过MIME类型判断
        mime_type, _ = mimetypes.guess_type(str(filepath))
        if mime_type and mime_type.startswith("text/"):
            return True

        # 尝试读取前1KB判断是否为二进制
        try:
            with open(filepath, "rb") as f:
                chunk = f.read(1024)
                # 检查是否包含空字节（二进制文件的特征）
                if b"\x00" in chunk:
                    return False
                # 检查是否为有效的UTF-8
                chunk.decode("utf-8")
                return True
        except:
            return False


# 全局实例
temp_file_manager = TempFileManager()
