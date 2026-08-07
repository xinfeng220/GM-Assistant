# -*- coding: utf-8 -*-
"""Agent 全局状态定义。

LangGraph 的 StateGraph 以 AgentState 作为节点间传递的状态 schema。
节点只读自己依赖的字段、写入自己的输出字段，共享同一份 state。
"""
from typing import Any, TypedDict

from src.core.schemas import Email, EmailClassified


class AgentState(TypedDict, total=False):
    route: str                  # 命名空间 route，如 "email.refresh"
    request: dict[str, Any]     # 请求参数
    capability: str             # 本次执行的能力名（如 "email"）
    emails: list[Email]         # 拉取结果（类型化，Task 2）
    classified: list[EmailClassified]
    messages: list[dict]        # 会话历史（Phase 2 启用）
    errors: list[str]           # 错误收集

    # Phase 2 追加：summaries / drafts / confirm_queue / sent_result
