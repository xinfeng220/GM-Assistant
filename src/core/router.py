# -*- coding: utf-8 -*-
"""路由解析：命名空间 route → 能力节点名。

当前由 route 表直接分发；Phase 2 演进为 LLM 意图分类（对应 supervisor.py），
resolve 接口保持 resolve(request) -> route。
"""
from src.core.orchestrator import orchestrator


def resolve(route: str) -> str | None:
    """返回 route 对应的能力节点名；未命中返回 None（超级图退化为 END）。"""
    return orchestrator.route_map().get(route)
