# -*- coding: utf-8 -*-
"""pytest 公共 fixture：强制 Mock 模式，杜绝测试触发真实 IMAP/LLM。"""
import pytest

from config import config


@pytest.fixture
def mock_env(monkeypatch):
    """把全局 config 改为 Mock 模式（无真实邮箱、规则分类）。"""
    monkeypatch.setattr(config, "IMAP_SERVER", "")
    monkeypatch.setattr(config, "IMAP_EMAIL", "")
    monkeypatch.setattr(config, "IMAP_PASSWORD", "")
    monkeypatch.setattr(config, "LLM_MODE", "mock")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    return config
