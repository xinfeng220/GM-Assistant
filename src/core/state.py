# -*- coding: utf-8 -*-
"""Agent 全局状态定义。

LangGraph 的 StateGraph 以 AgentState 作为节点间传递的状态 schema。
节点只读自己依赖的字段、写入自己的输出字段，共享同一份 state。
"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    route: str                  # router 选择的路径（如 refresh_email）
    request: dict[str, Any]     # 请求参数
    emails: list[dict]          # 拉取结果
    classified: list[dict]      # 分类结果
    messages: list[dict]        # 会话历史（替代原 memory.py）
    errors: list[str]           # 错误收集

    # Phase 2 追加：summaries / drafts / confirm_queue / sent_result
