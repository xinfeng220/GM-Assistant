# -*- coding: utf-8 -*-
from agent_core.graph import agent


def test_agent_refresh_email_flow(mock_env):
    result = agent.invoke(
        {"route": "refresh_email"},
        config={"configurable": {"thread_id": "test-refresh"}},
    )
    assert result["route"] == "refresh_email"
    assert result["emails"]
    assert len(result["classified"]) == len(result["emails"])
    assert "errors" not in result


def test_agent_unknown_route_ends(mock_env):
    result = agent.invoke(
        {"route": "nonsense"},
        config={"configurable": {"thread_id": "test-unknown"}},
    )
    assert "classified" not in result
