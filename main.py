# -*- coding: utf-8 -*-
"""Agent 平台总览页（Streamlit 首页）。

展示：已加载技能模块及状态、工具注册总数、安全模式、最近操作日志摘要。
"""
import streamlit as st

from src.core.logger import logger
from src.core.orchestrator import orchestrator
from src.core.safety import gateway
from src.core.tool_registry import registry
from src.core.config_manager import config
from src.core.tracing import tracer

st.set_page_config(page_title="GM-Assistant Agent 平台", page_icon="🤖", layout="wide")

st.title("🤖 GM-Assistant Agent 平台")
st.caption("可扩展技能插件平台 · Phase 1 最小闭环")

# 加载技能（首次调用触发扫描）
skills = orchestrator.get_all_skills()
tool_count = registry.count()

# ---------- 顶部指标 ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("技能模块", len(skills))
c2.metric("工具注册", tool_count)
c3.metric("安全模式", gateway.mode())
run = tracer.get_last_run()
c4.metric("最近执行", run["route"] if run else "—")

# ---------- 技能列表 ----------
st.subheader("🧩 已加载技能")
if not skills:
    st.warning("未发现任何技能。请确认 `src/capabilities/` 目录下存在 manifest.py。")
else:
    for skill in skills:
        with st.container(border=True):
            emoji = {"active": "🟢", "not_configured": "🟡", "error": "🔴"}.get(skill.status, "⚪")
            col_title, col_info, col_right = st.columns([2, 5, 3])
            col_title.markdown(f"### {emoji} {skill.title}")
            col_info.markdown(
                f"**{skill.name}** · v{skill.version or '—'}\n\n{skill.description}"
            )
            col_right.markdown(
                f"工具：{', '.join(skill.tools) if skill.tools else '—'}\n\n状态：`{skill.status}`"
            )
            if skill.hint:
                st.caption(f"配置：{skill.hint}")
            if skill.error:
                st.error(f"加载错误：{skill.error}")

# ---------- 安全网关说明 ----------
st.subheader("🛡️ 安全网关")
external_state = "已显式开启" if gateway.allow_write_external else "默认禁用"
st.markdown(
    "- **读操作**（read）：默认放行\n"
    "- **内部写**（write_internal）：需用户确认\n"
    "- **外部写**（write_external）：**默认禁用**，当前"
    f"「{external_state}」（配置 `ENABLE_WRITE_EXTERNAL=true` 才开启）\n"
    f"- 当前邮箱配置：{'已配置' if config.imap_configured else '未配置（Mock 模式）'} · "
    f"LLM：{config.LLM_MODEL}"
)

# ---------- 最近日志 ----------
st.subheader("📋 最近操作日志")
recent_logs = logger.recent(20)
if not recent_logs:
    st.caption("暂无日志")
for line in recent_logs:
    st.code(line)
