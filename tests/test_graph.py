# -*- coding: utf-8 -*-
from langgraph.graph import END

from src.core.graph import agent


def test_agent_email_refresh_flow(mock_env):
    result = agent.invoke(
        {"route": "email.refresh"},
        config={"configurable": {"thread_id": "test-refresh"}},
    )
    assert result["route"] == "email.refresh"
    assert result["emails"]
    assert len(result["classified"]) == len(result["emails"])
    assert "errors" not in result


def test_agent_unknown_route_ends(mock_env):
    result = agent.invoke(
        {"route": "nonsense"},
        config={"configurable": {"thread_id": "test-unknown"}},
    )
    assert "classified" not in result


def test_route_path_degrades_unbuilt_skill(mock_env, monkeypatch):
    """指向未装配子图技能的 route 应退化为 END，而不是报错。"""
    from src.core.graph import route_path
    from src.core.orchestrator import orchestrator

    monkeypatch.setattr(
        orchestrator,
        "route_map",
        lambda: {"email.refresh": "email", "broken.refresh": "broken_skill"},
    )
    valid = frozenset({END, "email"})
    assert route_path({"route": "broken.refresh"}, valid_targets=valid) == END
    assert route_path({"route": "email.refresh"}, valid_targets=valid) == "email"
    assert route_path({"route": "nonsense"}, valid_targets=valid) == END


def test_agent_invoke_degrades_unbuilt_skill(mock_env, monkeypatch):
    """整图 invoke 时，指向未装配子图技能的 route 不崩溃，直接结束。"""
    from src.core.orchestrator import orchestrator

    monkeypatch.setattr(
        orchestrator,
        "route_map",
        lambda: {"email.refresh": "email", "broken.refresh": "broken_skill"},
    )
    result = agent.invoke(
        {"route": "broken.refresh"},
        config={"configurable": {"thread_id": "test-broken"}},
    )
    assert result["route"] == "broken.refresh"
    assert "classified" not in result
