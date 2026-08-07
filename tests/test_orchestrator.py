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


def test_manifest_missing_route_subgraph_is_error(tmp_path):
    """ROUTES 非空但缺 build_subgraph → status=error，且不阻塞其他能力。"""
    from src.core.orchestrator import Orchestrator

    d = tmp_path / "broken"
    d.mkdir()
    (d / "manifest.py").write_text(
        "SKILL_META = {'name': 'broken'}\nROUTES = ['x']\n", encoding="utf-8"
    )
    o = Orchestrator()
    skills = o.scan(tmp_path)
    broken = next(s for s in skills if s.name == "broken")
    assert broken.status == "error"
    assert "build_subgraph" in broken.error


def test_manifest_missing_meta_name_is_error(tmp_path):
    from src.core.orchestrator import Orchestrator

    d = tmp_path / "noname"
    d.mkdir()
    (d / "manifest.py").write_text("ROUTES = []\n", encoding="utf-8")
    o = Orchestrator()
    skills = o.scan(tmp_path)
    bad = next(s for s in skills if s.name == "noname")
    assert bad.status == "error"
    assert "name" in bad.error
