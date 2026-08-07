# -*- coding: utf-8 -*-
"""email 技能子图：fetch → classify。

由 manifest.build_subgraph() 返回，orchestrator 装配到 Agent 超级图。
节点统一经 safety.safe_call 调用工具，异常进 state["errors"]，不崩图。
"""
from langgraph.graph import END, StateGraph

from src.core.logger import logger
from src.core.safety import safe_call
from src.core.state import AgentState


def fetch_node(state: AgentState) -> dict:
    try:
        emails = safe_call("fetch_emails")
        logger.info("email.graph", f"拉取 {len(emails)} 封邮件")
        return {"emails": emails}
    except Exception as e:
        logger.error("email.graph", f"拉取失败: {e}")
        return {"emails": [], "errors": [f"拉取失败: {e}"]}


def classify_node(state: AgentState) -> dict:
    emails = state.get("emails") or []
    try:
        classified = safe_call("classify_emails", emails=emails)
        logger.info("email.graph", f"分类完成 {len(classified)} 封")
        return {"classified": classified}
    except Exception as e:
        logger.error("email.graph", f"分类失败: {e}")
        return {"classified": [], "errors": [f"分类失败: {e}"]}


def build_email_subgraph():
    g = StateGraph(AgentState)
    g.add_node("fetch", fetch_node)
    g.add_node("classify", classify_node)
    g.set_entry_point("fetch")
    g.add_edge("fetch", "classify")
    g.add_edge("classify", END)
    return g.compile()
