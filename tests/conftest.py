# -*- coding: utf-8 -*-
"""pytest 公共 fixture：强制 Mock 模式，杜绝测试触发真实 IMAP/LLM。"""
import pytest

from src.core.config_manager import config


@pytest.fixture
def mock_env(monkeypatch):
    """把全局 config 改为 Mock 模式（无真实邮箱、规则分类）。"""
    monkeypatch.setattr(config, "IMAP_SERVER", "")
    monkeypatch.setattr(config, "IMAP_EMAIL", "")
    monkeypatch.setattr(config, "IMAP_PASSWORD", "")
    monkeypatch.setattr(config, "LLM_MODE", "mock")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    return config


@pytest.fixture(autouse=True)
def _isolate_registry():
    """快照并恢复全局工具注册中心。

    Orchestrator.scan() 会对全局 registry 执行 clear()；测试若用新
    Orchestrator 实例扫描临时目录，会把已注册的 email 工具清掉，导致后续
    test_pages 等测试在运行期经 safe_call 查不到工具。此 fixture 在每个测试
    前后快照/恢复 registry，隔离这种跨测试污染。
    """
    from src.core.tool_registry import registry

    snapshot = dict(registry.get_all())
    yield
    registry.clear()
    for definition in snapshot.values():
        registry.register_tool(definition)
