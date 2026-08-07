# -*- coding: utf-8 -*-
"""图执行可视化页：图结构 DAG + 最近执行轨迹 + token/工具审计 + 日志。"""
import streamlit as st

from src.core.logger import logger
from src.core.orchestrator import orchestrator
from src.core.tracing import tracer
from src.core.visualizer import render_graph_svg

st.set_page_config(page_title="图可视化", page_icon="📊", layout="wide")
st.title("📊 图执行可视化")

orchestrator.get_all_skills()

NODES = [
    {"name": "route", "label": "route\n入口"},
    {"name": "fetch_node", "label": "email.fetch\n拉取"},
    {"name": "classify_node", "label": "email.classify\n分类"},
]
EDGES = [("route", "fetch_node"), ("fetch_node", "classify_node")]

run = tracer.get_last_run()
executed = {n["node"]: n for n in run["nodes"]} if run else {}
svg = render_graph_svg(NODES, EDGES, executed)
st.subheader("图结构（已执行节点高亮）")
st.components.v1.html(svg, height=220)

st.subheader("最近一次执行")
if run:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("route", run["route"])
    c2.metric("节点数", len(run["nodes"]))
    c3.metric("token 用量", run["tokens"])
    c4.metric("兜底次数", len(run["fallbacks"]))
    st.caption("节点轨迹")
    st.dataframe(run["nodes"], use_container_width=True)
    if run["tools"]:
        st.caption("工具调用审计")
        st.dataframe(run["tools"], use_container_width=True)
else:
    st.info("尚无执行记录。去「📧 智能邮件处理」页点一次刷新即可看到。")

st.subheader("最近日志")
for line in logger.recent(15):
    st.code(line)
