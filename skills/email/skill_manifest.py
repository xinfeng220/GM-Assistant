# -*- coding: utf-8 -*-
"""邮件技能自描述文件。

声明技能元信息、工具与权限，供 agent_core.orchestrator 自动发现并加载。
新技能只需仿照本文件：SKILL_META + get_tools() + get_status()。
"""
from agent_core.tool_registry import TOOL_READ, ToolDefinition
from config import config
from skills.email.email_classifier import classify_emails
from skills.email.mail_fetcher import fetch_emails

# 本技能子图可处理的 route 名（orchestrator 据此构建超级图路由表）
ROUTES = ["refresh_email"]


def build_subgraph():
    """构建并返回本技能子图；由 orchestrator 装配到 Agent 超级图。"""
    from skills.email.graph import build_email_subgraph

    return build_email_subgraph()


# 技能元信息
SKILL_META = {
    "name": "email",
    "title": "智能邮件处理",
    "description": "拉取邮箱未读邮件，按紧急度/动作自动分类（Phase 1，不含草拟与发送）",
    "version": "0.1.0",
}


def get_tools() -> list[ToolDefinition]:
    """声明本技能提供的工具及其权限类型。"""
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


def get_status() -> str:
    """返回技能状态：active / not_configured。"""
    # Mock 模式下功能可完整演示，仍视为 active；配置缺失由 UI 提示
    return "active"


def get_config_hint() -> str:
    """返回当前配置状态提示，展示在总览页。"""
    hints = []
    if config.imap_configured:
        hints.append(f"IMAP 已配置（{config.IMAP_EMAIL}）")
    else:
        hints.append("IMAP 未配置 → 使用 Mock 样例邮件")
    if config.llm_configured:
        hints.append(f"LLM={config.LLM_MODEL}")
    else:
        hints.append("LLM 未配置 → 使用规则分类")
    return "；".join(hints)
