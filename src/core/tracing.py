# -*- coding: utf-8 -*-
"""执行观测：记录图执行轨迹、工具调用审计、token 用量。

进程内结构化缓冲，供可视化页展示（对应需求文档 6.3 审计日志）。
begin_run()/end_run() 之间为一次「当前运行」，record_* 写入当前运行；
未 begin_run 时 record_* 为 no-op，保证调用方无需判空。
"""
from collections import deque
from functools import wraps
from time import perf_counter


class TraceRecorder:
    def __init__(self, recent_maxlen: int = 200) -> None:
        self._recent_maxlen = recent_maxlen
        self._runs: deque[dict] = deque(maxlen=recent_maxlen)
        self._current: dict | None = None

    # ---------- 运行生命周期 ----------
    def begin_run(self, route: str) -> None:
        self._current = {
            "route": route,
            "nodes": [],
            "tools": [],
            "tokens": 0,
            "fallbacks": [],
        }

    def end_run(self) -> None:
        if self._current is not None:
            self._runs.append(self._current)
        self._current = None

    # ---------- 记录 ----------
    def record_node(self, node: str, status: str, duration_ms: float, detail: str = "") -> None:
        if self._current is None:
            return
        self._current["nodes"].append({
            "node": node, "status": status, "duration_ms": round(duration_ms, 1), "detail": detail,
        })

    def record_tool(self, tool: str, status: str) -> None:
        if self._current is None:
            return
        self._current["tools"].append({"tool": tool, "status": status})

    def record_tokens(self, n: int) -> None:
        if self._current is None:
            return
        self._current["tokens"] += int(n)

    def record_fallback(self, label: str = "") -> None:
        if self._current is None:
            return
        self._current["fallbacks"].append(label)

    # ---------- 查询 ----------
    def get_last_run(self) -> dict | None:
        return self._runs[-1] if self._runs else None

    def recent_runs(self, n: int) -> list[dict]:
        return list(self._runs)[-n:]


# 全局单例
tracer = TraceRecorder()


def traced(*, target: "TraceRecorder | None" = None):
    """包裹图节点：计时并记录执行轨迹。缺省记录到全局 tracer。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(state):
            rec = target if target is not None else tracer
            start = perf_counter()
            result = fn(state)
            duration_ms = (perf_counter() - start) * 1000
            if rec is not None:
                status = "error" if (result or {}).get("errors") else "ok"
                rec.record_node(fn.__name__, status, duration_ms)
            return result
        return wrapper
    return decorator
