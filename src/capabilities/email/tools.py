# -*- coding: utf-8 -*-
"""email 能力声明的工具（fetch_emails / classify_emails）。

工具句柄指向 fetcher/classifier 的模块级函数；权限类型在此集中声明。
"""
from src.capabilities.email.classifier import classify_emails
from src.capabilities.email.fetcher import fetch_emails
from src.core.tool_registry import TOOL_READ, ToolDefinition


def get_tools() -> list[ToolDefinition]:
    """声明本能力提供的工具及其权限类型。"""
    return [
        ToolDefinition(
            name="fetch_emails",
            tool_type=TOOL_READ,
            module="email",
            description="从 IMAP 邮箱拉取最近未读邮件（未配置时使用 Mock 样例）",
            handler=fetch_emails,
            requires_config=["IMAP_SERVER", "IMAP_EMAIL", "IMAP_PASSWORD"],
        ),
        ToolDefinition(
            name="classify_emails",
            tool_type=TOOL_READ,
            module="email",
            description="对邮件列表进行 LLM/规则分类",
            handler=classify_emails,
        ),
    ]
