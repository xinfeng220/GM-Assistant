# -*- coding: utf-8 -*-
from src.core.state import AgentState


def test_agent_state_partial_fields():
    s = AgentState(route="email.refresh", emails=[], classified=[])
    assert s["route"] == "email.refresh"
    assert s.get("errors") is None  # total=False 允许缺省字段
