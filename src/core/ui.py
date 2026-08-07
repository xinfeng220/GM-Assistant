# -*- coding: utf-8 -*-
"""平台级 Streamlit UI 组件：全站右侧可折叠可视化面板。

viz_layout(): 页面顶部调用，渲染「显示可视化」toggle + 左右列布局（折叠时右列为 None）；
render_visualization_panel(): 在右列内渲染 图结构 DAG + 最近执行指标 + 节点轨迹/工具调用审计。

图结构常量暂为 email 能力（_DEFAULT_NODES/_DEFAULT_EDGES），
Phase 2 由 orchestrator 按能力动态导出；render_visualization_panel(nodes=..., edges=...) 参数已预留。
"""
import streamlit as st

from src.core.tracing import tracer
from src.core.visualizer import render_graph_svg

# 当前平台唯一能力为 email，图结构暂以常量给出（Phase 2 由 orchestrator 动态导出）
_DEFAULT_NODES = [
    {"name": "route", "label": "route\n入口"},
    {"name": "fetch_node", "label": "email.fetch\n拉取"},
    {"name": "classify_node", "label": "email.classify\n分类"},
]
_DEFAULT_EDGES = [("route", "fetch_node"), ("fetch_node", "classify_node")]

# 窄面板紧凑渲染参数（与 Task 1 的 test_compact_params_produce_narrow_svg 一致）
_COMPACT = dict(box_w=96, box_h=46, gap_x=22, gap_y=32, margin=14,
                font_size=11, font_size_sub=9)

# 右列吸顶：以面板内 #viz-panel-anchor 标记定位，只作用于可视化面板所在列（避免误伤页内其他 st.columns 的第二列）。
# 浏览器不支持 :has() 时选择器失效 → 面板随页滚动（不影响功能）。
_PANEL_CSS = """
<style>
[data-testid="stColumn"]:has(#viz-panel-anchor) {
    position: sticky;
    top: 0.75rem;
    align-self: flex-start;
}
</style>
"""


def viz_layout(ratio: list | tuple | None = None) -> tuple[bool, object, object | None]:
    """页面顶部调用：渲染「显示可视化」toggle + 左右列布局。

    返回 (show_vis, left, right)：show_vis=False 时 right=None，left 为全宽容器。
    """
    if ratio is None:
        ratio = [2.6, 1.4]
    st.markdown(_PANEL_CSS, unsafe_allow_html=True)
    show_vis = st.toggle("显示可视化", value=True, key="viz_show")
    if show_vis:
        left, right = st.columns(list(ratio))
    else:
        left = st.container()
        right = None
    return show_vis, left, right


def render_visualization_panel(nodes: list[dict] | None = None,
                               edges: list[tuple[str, str]] | None = None) -> None:
    """在右列内渲染可视化面板：图结构 + 最近执行指标 + 节点轨迹/工具调用审计。"""
    nodes = nodes if nodes is not None else _DEFAULT_NODES
    edges = edges if edges is not None else _DEFAULT_EDGES
    run = tracer.get_last_run()

    # sticky 定位标记：CSS 仅吸顶「包含该标记的列」
    st.markdown('<div id="viz-panel-anchor"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("### 📊 图执行可视化")
        executed = {n["node"]: n for n in run["nodes"]} if run else {}
        svg = render_graph_svg(nodes, edges, executed, **_COMPACT)
        st.components.v1.html(svg, height=100)
        if run is None:
            st.caption("尚无执行记录，去「📧 智能邮件处理」页点一次刷新即可看到。")
            return
        r1a, r1b = st.columns(2)
        r1a.metric("route", run["route"])
        r1b.metric("节点数", len(run["nodes"]))
        r2a, r2b = st.columns(2)
        r2a.metric("token 用量", run["tokens"])
        r2b.metric("兜底次数", len(run["fallbacks"]))
        st.caption("节点轨迹")
        st.dataframe(run["nodes"], use_container_width=True, height=140)
        if run["tools"]:
            st.caption("工具调用审计")
            st.dataframe(run["tools"], use_container_width=True, height=100)
