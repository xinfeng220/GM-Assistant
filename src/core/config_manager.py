# -*- coding: utf-8 -*-
"""全局配置：settings.yaml + .env 覆盖 + prompt 模板缓存。

- 非敏感运行参数放 config/settings.yaml（默认值来源）。
- 密钥（IMAP 密码、API Key 等）只在 .env，绝不入 yaml。
- 取值优先级：环境变量 > settings.yaml > 代码默认值。
- config 为全局单例；get_prompt() 线程安全缓存读取 config/prompts/。
"""
import functools
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录（src/core/config_manager.py: parents[2] = 根）
BASE_DIR = Path(__file__).resolve().parents[2]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


class Config:
    """全部配置项；来源 yaml + 环境变量。"""

    def __init__(self) -> None:
        load_dotenv(BASE_DIR / ".env")
        self._yaml = self._load_yaml()

        # ---------- LLM ----------
        self.LLM_MODE = os.getenv("LLM_MODE") or self._yaml["llm"]["mode"]
        self.LLM_MODEL = os.getenv("LLM_MODEL") or self._yaml["llm"]["model"]
        self.LLM_BASE_URL = os.getenv("LLM_BASE_URL") or self._yaml["llm"]["base_url"]
        self.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        self.LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or self._yaml["llm"]["temperature"])

        # ---------- 邮箱 (IMAP)，密钥仅来自环境 ----------
        self.IMAP_SERVER = os.getenv("IMAP_SERVER", "")
        self.IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
        self.IMAP_EMAIL = os.getenv("IMAP_EMAIL", "")
        self.IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
        self.IMAP_USE_SSL = _as_bool(os.getenv("IMAP_USE_SSL"), True)
        self.EMAIL_FETCH_LIMIT = int(os.getenv("EMAIL_FETCH_LIMIT") or self._yaml["email"]["fetch_limit"])
        self.EMAIL_BODY_PREVIEW_LEN = int(os.getenv("EMAIL_BODY_PREVIEW_LEN") or self._yaml["email"]["body_preview_len"])

        # ---------- 安全网关 ----------
        self.ENABLE_WRITE_EXTERNAL = _as_bool(
            os.getenv("ENABLE_WRITE_EXTERNAL"), self._yaml["safety"]["enable_write_external"]
        )

        # ---------- 观测 ----------
        self.TRACING_ENABLED = bool(self._yaml["tracing"]["enabled"])
        self.TRACING_RECENT_MAXLEN = int(self._yaml["tracing"]["recent_maxlen"])

    @staticmethod
    def _load_yaml() -> dict:
        with open(BASE_DIR / "config" / "settings.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ---------- 便捷判断 ----------
    @property
    def imap_configured(self) -> bool:
        return bool(self.IMAP_SERVER and self.IMAP_EMAIL and self.IMAP_PASSWORD)

    @property
    def llm_configured(self) -> bool:
        return self.LLM_MODE == "real" and bool(self.LLM_API_KEY)

    # ---------- prompt 模板 ----------
    @functools.lru_cache(maxsize=64)
    def get_prompt(self, name: str) -> str:
        """按「能力.名」读取 config/prompts/<能力>/<名>.txt（UTF-8，带缓存）。"""
        rel = name.replace(".", "/")
        return (BASE_DIR / "config" / "prompts" / f"{rel}.txt").read_text(encoding="utf-8")


# 全局单例
config = Config()
