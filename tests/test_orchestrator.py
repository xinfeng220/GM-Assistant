# -*- coding: utf-8 -*-
from src.core.orchestrator import orchestrator


def test_scan_builds_email_subgraph(mock_env):
    skills = orchestrator.scan()
    email = next(s for s in skills if s.name == "email")
    assert email.status == "active"
    assert email.subgraph is not None
    assert "refresh" in email.routes


def test_route_map_maps_email_refresh(mock_env):
    orchestrator.scan()
    assert orchestrator.route_map()["email.refresh"] == "email"
