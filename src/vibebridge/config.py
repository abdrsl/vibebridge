"""Unified configuration for VibeBridge."""

from __future__ import annotations

import os
import re
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
    model: str = "deepseek/deepseek-reasoner"
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


class OpenRouterProviderConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    default_model: str = "openai/gpt-4o"
    base_url: str = "https://openrouter.ai/api/v1"


class AgentsConfig(BaseModel):
    default_provider: str = "opencode"
    opencode: OpenCodeProviderConfig = Field(default_factory=OpenCodeProviderConfig)
    openclaw: OpenClawProviderConfig = Field(default_factory=OpenClawProviderConfig)
    kimi: KimiProviderConfig = Field(default_factory=KimiProviderConfig)
    claude: ClaudeProviderConfig = Field(default_factory=ClaudeProviderConfig)
    openrouter: OpenRouterProviderConfig = Field(default_factory=OpenRouterProviderConfig)


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


def _expand_env_vars(obj: Any) -> Any:
    """Recursively replace ${VAR} placeholders with environment variable values."""
    if isinstance(obj, str):
        def _repl(match: re.Match) -> str:
            return os.environ.get(match.group(1), match.group(0))
        return re.sub(r"\$\{([^}]+)\}", _repl, obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    return obj


def _remove_unresolved_placeholders(obj: Any) -> Any:
    """Remove ${VAR} strings that were not expanded so defaults/env vars win."""
    if isinstance(obj, str):
        if re.fullmatch(r"\$\{[^}]+\}", obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: v for k, v in ((k, _remove_unresolved_placeholders(v)) for k, v in obj.items()) if v is not None}
    if isinstance(obj, list):
        return [i for i in (_remove_unresolved_placeholders(i) for i in obj) if i is not None]
    return obj


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Merge overlay into base recursively."""
    result = base.copy()
    for k, v in overlay.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _apply_flat_env_overrides(data: dict) -> dict:
    """Map commonly-used flat env vars (e.g. FEISHU_APP_ID) into nested dict."""
    mappings = {
        "FEISHU_APP_ID": ("feishu", "app_id"),
        "FEISHU_APP_SECRET": ("feishu", "app_secret"),
        "FEISHU_ENCRYPT_KEY": ("feishu", "encrypt_key"),
        "FEISHU_VERIFICATION_TOKEN": ("feishu", "verification_token"),
        "FEISHU_MODE": ("feishu", "mode"),
        "VB_DEFAULT_PROVIDER": ("agents", "default_provider"),
        "OPENROUTER_API_KEY": ("agents", "openrouter", "api_key"),
    }
    for env_key, path in mappings.items():
        val = os.getenv(env_key)
        if val is not None:
            node = data
            for key in path[:-1]:
                node = node.setdefault(key, {})
            node[path[-1]] = val
    return data


def load_config() -> Config:
    """Load configuration from defaults, then YAML, then environment variables.

    Priority (highest -> lowest):
    1. Environment variables (flat names like FEISHU_APP_ID or nested like FEISHU__APP_ID)
    2. YAML config file with ${VAR} placeholders expanded
    3. Built-in defaults
    """
    # Step 1: pydantic-settings loads .env and environment variables automatically
    cfg = Config()

    # Step 2: if YAML exists, merge it in without clobbering env vars
    if cfg.config_file.exists():
        import yaml

        with cfg.config_file.open("r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        # Expand ${VAR} syntax inside YAML values
        raw_data = _expand_env_vars(raw_data)
        # Also inject commonly-used flat env vars so README examples work out of the box
        raw_data = _apply_flat_env_overrides(raw_data)
        # Drop placeholders that weren't expanded so env/defaults take over
        raw_data = _remove_unresolved_placeholders(raw_data)

        # Merge YAML on top of current config (which already contains env vars).
        # This means a real value in YAML wins, but an empty/missing YAML value
        # leaves the env var intact.
        current = cfg.model_dump()
        merged = _deep_merge(current, raw_data or {})
        cfg = Config(**merged)

    cfg.ensure_dirs()
    return cfg


# Global cached instance
_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance
