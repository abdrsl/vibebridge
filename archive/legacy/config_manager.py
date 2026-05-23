"""
配置管理器
管理系统配置，如 WebSocket/webhook 模式切换
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """配置管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 配置文件路径
        project_dir = Path(__file__).parent.parent.parent
        self.config_path = project_dir / "config" / "settings.json"

        # 默认配置
        self.default_config = {
            "version": "1.0",
            "feishu_mode": "websocket",  # "websocket" 或 "webhook"
            "websocket_enabled": True,
            "last_updated": datetime.now().isoformat(),
            "description": "OpenCode-Feishu Bridge 系统配置",
        }

        # 当前配置
        self.config = self.default_config.copy()

        # 加载配置
        self.load_config()

        self._initialized = True

    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)

                # 合并配置，保留新字段
                for key, value in loaded_config.items():
                    self.config[key] = value

                # 确保必需字段存在
                for key in ["feishu_mode", "websocket_enabled"]:
                    if key not in self.config:
                        self.config[key] = self.default_config[key]

                print(f"[Config] 加载配置文件: {self.config_path}")
                return True
            else:
                # 创建默认配置
                print(f"[Config] 配置文件不存在，创建默认配置: {self.config_path}")
                self.save_config()
                return True
        except Exception as e:
            print(f"[Config] 加载配置文件失败: {e}")
            return False

    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # 更新最后修改时间
            self.config["last_updated"] = datetime.now().isoformat()

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            print(f"[Config] 配置文件已保存: {self.config_path}")
            return True
        except Exception as e:
            print(f"[Config] 保存配置文件失败: {e}")
            return False

    def get(self, key: str, default=None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """设置配置项"""
        self.config[key] = value

        if save:
            return self.save_config()
        return True

    def get_feishu_mode(self) -> str:
        """获取飞书交互模式"""
        return self.config.get("feishu_mode", "websocket")

    def set_feishu_mode(self, mode: str, save: bool = True) -> bool:
        """设置飞书交互模式

        Args:
            mode: "websocket" 或 "webhook"
            save: 是否立即保存
        """
        if mode not in ["websocket", "webhook"]:
            print(f"[Config] 无效的模式: {mode}，必须为 'websocket' 或 'webhook'")
            return False

        self.config["feishu_mode"] = mode
        self.config["websocket_enabled"] = mode == "websocket"

        if save:
            return self.save_config()
        return True

    def is_websocket_enabled(self) -> bool:
        """检查 WebSocket 是否启用"""
        return self.config.get("websocket_enabled", True)

    def enable_websocket(self, save: bool = True) -> bool:
        """启用 WebSocket 模式"""
        return self.set_feishu_mode("websocket", save)

    def disable_websocket(self, save: bool = True) -> bool:
        """禁用 WebSocket 模式（使用 webhook）"""
        return self.set_feishu_mode("webhook", save)

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "feishu_mode": self.get_feishu_mode(),
            "websocket_enabled": self.is_websocket_enabled(),
            "last_updated": self.get("last_updated"),
            "description": self.get("description", ""),
        }


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    return ConfigManager()


# 测试代码
if __name__ == "__main__":
    config = get_config_manager()

    print("当前配置:")
    print(json.dumps(config.get_config_summary(), indent=2, ensure_ascii=False))

    # 测试模式切换
    print("\n切换到 webhook 模式...")
    config.set_feishu_mode("webhook")

    print("切换后配置:")
    print(json.dumps(config.get_config_summary(), indent=2, ensure_ascii=False))

    # 切换回 websocket
    print("\n切换回 websocket 模式...")
    config.set_feishu_mode("websocket")

    print("最终配置:")
    print(json.dumps(config.get_config_summary(), indent=2, ensure_ascii=False))
