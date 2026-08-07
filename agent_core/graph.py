# -*- coding: utf-8 -*-
"""Agent 超级图：入口 router 节点 + 各技能子图。

build_agent_graph() 装配超级图并编译；agent 为全局单例。
UI 统一通过 agent.invoke({"route": ...}) 驱动，不再直接调用工具。
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent_core.logger import logger
from agent_core.orchestrator import orchestrator
from agent_core.state import AgentState


def route_node(state: AgentState) -> dict:
    """入口节点：记录路由并原样透传 state（实际分发在条件边完成）。"""
    route = state.get("route") or "unknown"
    logger.info("agent.graph", f"路由分发: {route}")
    return {}


def route_path(state: AgentState):
    """根据 route 决定进入哪个技能子图；未知 route 直接结束。"""
    return orchestrator.route_map().get(state.get("route"), END)


def build_agent_graph():
    g = StateGraph(AgentState)
    g.add_node("route", route_node)

    route_map = {}
    for skill in orchestrator.get_all_skills():
        if skill.subgraph is not None:
            g.add_node(skill.name, skill.subgraph)
            route_map[skill.name] = skill.name

    path_map = {**route_map, END: END}
    g.add_conditional_edges("route", route_path, path_map)
    g.set_entry_point("route")
    return g.compile(checkpointer=MemorySaver())


# 全局单例（进程启动时扫描并装配）
agent = build_agent_graph()
