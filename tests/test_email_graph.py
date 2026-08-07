# -*- coding: utf-8 -*-
import pytest

from src.core.orchestrator import orchestrator


@pytest.fixture(autouse=True, scope="module")
def _register_skill_tools():
    """把 src/capabilities/ 声明的工具注册进全局 registry（子图节点经 safe_call 调用）。"""
    orchestrator.scan()


from src.capabilities.email.graph import build_email_subgraph
from src.capabilities.email.manifest import ROUTES, build_subgraph


def test_manifest_exposes_route_and_subgraph(mock_env):
    assert "refresh" in ROUTES
    assert build_subgraph() is not None


def test_email_subgraph_refresh_flow(mock_env):
    graph = build_email_subgraph()
    result = graph.invoke({"route": "email.refresh"})
    assert result["emails"]            # Mock 8 封
    assert len(result["classified"]) == len(result["emails"])
