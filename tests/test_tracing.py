# -*- coding: utf-8 -*-
from src.core.tracing import TraceRecorder


def _fresh():
    r = TraceRecorder()
    r.begin_run("email.refresh")
    return r


def test_record_and_last_run():
    r = _fresh()
    r.record_node("fetch", "ok", 12.0)
    r.record_tool("fetch_emails", "ok")
    r.record_tokens(150)
    r.end_run()
    run = r.get_last_run()
    assert run["route"] == "email.refresh"
    assert len(run["nodes"]) == 1
    assert run["nodes"][0]["node"] == "fetch"
    assert run["tokens"] == 150


def test_no_current_run_is_noop():
    r = TraceRecorder()
    r.record_tokens(10)  # 未 begin_run，不应崩
    r.record_node("n", "ok", 1.0)
    assert r.get_last_run() is None


def test_recent_runs_bounded():
    r = TraceRecorder(recent_maxlen=2)
    for i in range(3):
        r.begin_run(f"r{i}")
        r.end_run()
    assert len(r.recent_runs(10)) == 2
    assert r.recent_runs(1)[0]["route"] == "r2"


def test_traced_decorator_records_node():
    from src.core.tracing import TraceRecorder, traced

    r = TraceRecorder()
    r.begin_run("email.refresh")

    @traced(target=r)
    def fetch_node(state):
        return {"emails": []}

    fetch_node({})
    r.end_run()
    run = r.get_last_run()
    assert run["nodes"][0]["node"] == "fetch_node"
    assert run["nodes"][0]["status"] == "ok"


def test_tracing_disabled_gates_recording(monkeypatch):
    from src.core.config_manager import config
    from src.core.tracing import TraceRecorder

    monkeypatch.setattr(config, "TRACING_ENABLED", False)
    r = TraceRecorder()
    r.begin_run("email.refresh")
    r.record_node("fetch_node", "ok", 1.0)
    r.end_run()
    assert r.get_last_run() is None
    assert r.recent_runs(5) == []
