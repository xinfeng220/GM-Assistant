# -*- coding: utf-8 -*-
"""全局配置：从 .env 读取环境变量，集中提供配置项。

敏感信息（邮箱密码、API Key 等）一律只从 .env / 环境变量读取，绝不硬编码。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（config_manager.py: src/core/ → 根）
BASE_DIR = Path(__file__).resolve().parents[2]

# 加载 .env 文件（若存在）
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    """把字符串环境变量解析为布尔值。"""
    if not value:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


class Config:
    """全部配置项；未在 .env 中设置时使用默认值。"""

    # ---------- 邮箱 (IMAP) ----------
    IMAP_SERVER: str = os.getenv("IMAP_SERVER", "")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_EMAIL: str = os.getenv("IMAP_EMAIL", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    IMAP_USE_SSL: bool = _as_bool(os.getenv("IMAP_USE_SSL"), True)
    EMAIL_FETCH_LIMIT: int = int(os.getenv("EMAIL_FETCH_LIMIT", "20"))
    EMAIL_BODY_PREVIEW_LEN: int = int(os.getenv("EMAIL_BODY_PREVIEW_LEN", "300"))

    # ---------- LLM 分类 (litellm) ----------
    LLM_MODE: str = os.getenv("LLM_MODE", "mock")          # mock / real
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")

    # ---------- 安全网关 ----------
    ENABLE_WRITE_EXTERNAL: bool = _as_bool(os.getenv("ENABLE_WRITE_EXTERNAL"), False)

    # ---------- 便捷判断 ----------
    @property
    def imap_configured(self) -> bool:
        """是否配置了真实 IMAP 邮箱（服务器/账号/密码三者齐全）。"""
        return bool(self.IMAP_SERVER and self.IMAP_EMAIL and self.IMAP_PASSWORD)

    @property
    def llm_configured(self) -> bool:
        """是否配置了真实 LLM：LLM_MODE=real 且已填写 API Key。"""
        return self.LLM_MODE == "real" and bool(self.LLM_API_KEY)


# 全局单例
config = Config()
