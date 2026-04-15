"""Unified configuration for VibeBridge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeishuConfig(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""
    verification_token: str = ""
    mode: str = "websocket"  # "websocket" | "webhook"
    webhook_url: str | None = None  # for webhook mode
    group_allowlist: list[str] = Field(default_factory=list)
    user_allowlist: list[str] = Field(default_factory=list)


class OpenCodeProviderConfig(BaseModel):
    enabled: bool = True
    binary: str = "auto"
    model: str = "deepseek/deepseek-chat"
    default_workdir: str = "~/workspace"


class OpenClawProviderConfig(BaseModel):
    enabled: bool = False
    gateway_url: str = "http://127.0.0.1:18789"


class KimiProviderConfig(BaseModel):
    enabled: bool = False
    acp_url: str = "http://127.0.0.1:9876"


class ClaudeProviderConfig(BaseModel):
    enabled: bool = False
    binary: str = "auto"


class AgentsConfig(BaseModel):
    default_provider: str = "opencode"
    opencode: OpenCodeProviderConfig = Field(default_factory=OpenCodeProviderConfig)
    openclaw: OpenClawProviderConfig = Field(default_factory=OpenClawProviderConfig)
    kimi: KimiProviderConfig = Field(default_factory=KimiProviderConfig)
    claude: ClaudeProviderConfig = Field(default_factory=ClaudeProviderConfig)


class ApprovalRule(BaseModel):
    provider: str = "*"
    pattern: str = ".*"
    level: str = "low"


class ApprovalConfig(BaseModel):
    enabled: bool = True
    default_level: str = "low"
    rules: list[ApprovalRule] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Runtime paths
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".config" / "vibebridge")
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".local" / "share" / "vibebridge" / "data")
    log_dir: Path = Field(default_factory=lambda: Path.home() / ".local" / "share" / "vibebridge" / "logs")

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.yaml"

    def ensure_dirs(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Load configuration from defaults, then YAML, then environment variables."""
    cfg = Config()

    # Load from YAML if exists
    if cfg.config_file.exists():
        import yaml

        with cfg.config_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = Config(**data)

    cfg.ensure_dirs()
    return cfg


# Global cached instance
_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance
