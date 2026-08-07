# -*- coding: utf-8 -*-
"""邮件技能的 Streamlit 页面（由 pages/02_email.py 转发调用）。

功能：点「刷新邮件」触发拉取 + 分类，按紧急度分组展示，可展开看详情。
结果保存在 st.session_state，避免重复拉取。
"""
from datetime import datetime

import streamlit as st

from src.core.logger import logger
from src.core.config_manager import config
from src.core.tracing import tracer
from src.core.ui import viz_layout, render_visualization_panel

# 分组展示顺序与图标
_URGENCY_ORDER = ["紧急", "重要", "普通", "可忽略"]
_URGENCY_EMOJI = {"紧急": "🔴", "重要": "🟡", "普通": "🟢", "可忽略": "⚪"}

# 会话状态键
_KEY_EMAILS = "email_emails"
_KEY_LAST_REFRESH = "email_last_refresh"
_KEY_LAST_COUNT = "email_last_count"


def render() -> None:
    """渲染邮件处理页面。"""
    st.title("📧 智能邮件处理")
    st.caption("Phase 1：邮件拉取 + 自动分类（Mock / IMAP）· **不含草拟与发送**")

    _, left, right = viz_layout()
    with left:
        _show_mode_banner()

        # 顶部：刷新按钮 + 状态
        col_btn, col_status = st.columns([1, 3])
        with col_btn:
            if st.button("🔄 刷新邮件", type="primary", use_container_width=True):
                _refresh()
        with col_status:
            st.caption(_refresh_status())

        emails = st.session_state.get(_KEY_EMAILS)
        if not emails:
            st.info("点击「🔄 刷新邮件」开始。未配置邮箱时将使用 Mock 样例邮件演示。")
        else:
            st.divider()
            _render_groups(emails)

    if right is not None:
        with right:
            render_visualization_panel()


def _show_mode_banner() -> None:
    """根据配置提示当前运行模式。"""
    banners = []
    if not config.imap_configured:
        banners.append("🧪 未配置真实 IMAP，当前使用 **Mock 样例邮件**。可在 `.env` 填写邮箱后切换。")
    if not config.llm_configured:
        banners.append("🤖 LLM 未配置，当前使用 **规则分类**。设置 `LLM_MODE=real` 与 `LLM_API_KEY` 后启用真实模型。")
    if banners:
        st.info("\n\n".join(banners))


def _refresh() -> None:
    """触发 Agent 超级图执行「刷新邮件」路径。"""
    from src.core.graph import agent

    with st.spinner("正在拉取并分类邮件..."):
        tracer.begin_run("email.refresh")
        try:
            result = agent.invoke(
                {"route": "email.refresh"},
                config={"configurable": {"thread_id": "ui"}},
            )
            classified = result.get("classified") or []
            st.session_state[_KEY_EMAILS] = classified
            st.session_state[_KEY_LAST_REFRESH] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state[_KEY_LAST_COUNT] = len(classified)
            logger.info("email.ui_page", f"刷新完成，共 {len(classified)} 封邮件")
            for err in result.get("errors") or []:
                st.warning(err)
        except Exception as e:
            logger.error("email.ui_page", f"刷新失败: {e}")
            st.error(f"刷新失败：{e}")
        finally:
            tracer.end_run()
    st.rerun()


def _refresh_status() -> str:
    if _KEY_LAST_REFRESH not in st.session_state:
        return "尚未刷新"
    return f"最近刷新：{st.session_state[_KEY_LAST_REFRESH]} ｜ 共 {st.session_state.get(_KEY_LAST_COUNT, 0)} 封"


def _render_groups(emails: list) -> None:
    """按紧急度分组展示邮件列表。"""
    groups: dict[str, list] = {}
    for item in emails:
        urgency = item.classification.urgency
        groups.setdefault(urgency, []).append(item)

    for urgency in _URGENCY_ORDER:
        items = groups.get(urgency, [])
        st.markdown(f"### {_URGENCY_EMOJI.get(urgency, '⚪')} {urgency}（{len(items)} 封）")
        if not items:
            st.caption("—")
            continue
        for item in items:
            _render_email(item)


def _render_email(item) -> None:
    """渲染单封邮件（可展开）。"""
    subject = item.subject or "（无主题）"
    sender = item.from_ or "未知发件人"
    received = item.received_at or ""
    cls = item.classification

    with st.expander(f"{subject}　—　{sender}　（{received}）"):
        st.markdown(
            f"**分类**：`{cls.urgency}` / `{cls.action}`　"
            f"**标签**：`{cls.category_tag}`"
        )
        st.markdown(f"**理由**：{cls.reason}")
        st.divider()
        st.markdown("**邮件预览**")
        st.write(item.body_preview or "（无正文）")
