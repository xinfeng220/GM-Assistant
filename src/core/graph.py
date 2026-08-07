# -*- coding: utf-8 -*-
"""Agent 超级图：入口 router 节点 + 各技能子图。

build_agent_graph() 装配超级图并编译；agent 为全局单例。
UI 统一通过 agent.invoke({"route": ...}) 驱动，不再直接调用工具。
"""
from functools import partial

from langgraph.graph import END, StateGraph

from src.core.checkpointer import build_checkpointer
from src.core.logger import logger
from src.core.orchestrator import orchestrator
from src.core.state import AgentState


def route_node(state: AgentState) -> dict:
    """入口节点：记录路由并原样透传 state（实际分发在条件边完成）。"""
    route = state.get("route") or "unknown"
    logger.info("agent.graph", f"路由分发: {route}")
    return {}


def route_path(state: AgentState, valid_targets: frozenset[str]) -> str:
    """根据 route 决定进入哪个技能子图。

    valid_targets 是实际装配进超级图的节点名集合；指向未装配技能
    （子图构建失败 / 仅声明 ROUTES 无子图）的 route 一律退化为 END，
    保证单技能故障不拖垮整个 Agent 图。
    """
    target = orchestrator.route_map().get(state.get("route"))
    if target is not None and target in valid_targets:
        return target
    return END


def build_agent_graph():
    g = StateGraph(AgentState)
    g.add_node("route", route_node)

    route_map = {}
    valid_targets = {END}
    for skill in orchestrator.get_all_skills():
        if skill.subgraph is not None:
            g.add_node(skill.name, skill.subgraph)
            route_map[skill.name] = skill.name
            valid_targets.add(skill.name)

    path_map = {**route_map, END: END}
    g.add_conditional_edges(
        "route",
        partial(route_path, valid_targets=frozenset(valid_targets)),
        path_map,
    )
    g.set_entry_point("route")
    return g.compile(checkpointer=build_checkpointer())


# 全局单例（进程启动时扫描并装配）
agent = build_agent_graph()
