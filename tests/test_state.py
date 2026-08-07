# -*- coding: utf-8 -*-
from agent_core.state import AgentState


def test_agent_state_partial_fields():
    s = AgentState(route="refresh_email", emails=[], classified=[])
    assert s["route"] == "refresh_email"
    assert s.get("errors") is None  # total=False 允许缺省字段
