# -*- coding: utf-8 -*-
"""图结构 SVG 渲染（零依赖）。

节点为矩形盒、边为箭头；已执行节点绿色高亮并标耗时。
供 Streamlit 经 st.components.v1.html 展示。
"""


def _layers(nodes: list[dict], edges: list[tuple[str, str]]) -> dict[str, int]:
    """按拓扑分层：source 层 < target 层。"""
    layer = {node["name"]: 0 for node in nodes}
    changed = True
    while changed:
        changed = False
        for src, dst in edges:
            if layer.get(src, 0) + 1 > layer.get(dst, 0):
                layer[dst] = layer[src] + 1
                changed = True
    return layer


def render_graph_svg(nodes: list[dict], edges: list[tuple[str, str]],
                     executed: dict[str, dict] | None = None) -> str:
    """渲染 DAG 为 SVG 字符串。

    nodes: [{"name": ..., "label": ...}]；edges: [(src, dst), ...]
    executed: {node_name: {"duration_ms": float, "status": str}}
    """
    executed = executed or {}
    layers = _layers(nodes, edges)
    box_w, box_h, gap_x, gap_y, margin = 150, 48, 60, 40, 20
    by_layer: dict[int, list[str]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node["name"]], []).append(node["name"])
    max_cols = max(len(v) for v in by_layer.values())
    pos: dict[str, tuple[int, int]] = {}
    for name, lst in by_layer.items():
        for i, node_name in enumerate(lst):
            pos[node_name] = (
                margin + layers[node_name] * (box_w + gap_x),
                margin + i * (box_h + gap_y),
            )
    max_layer = max(layers.values())
    width = margin * 2 + (max_layer + 1) * box_w + max_layer * gap_x
    height = margin * 2 + max_cols * box_h + (max_cols - 1) * gap_y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
        'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#666"/></marker></defs>',
    ]
    for src, dst in edges:
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        parts.append(
            f'<line x1="{x1 + box_w}" y1="{y1 + box_h // 2}" x2="{x2}" y2="{y2 + box_h // 2}" '
            'stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>'
        )
    for node in nodes:
        x, y = pos[node["name"]]
        ex = executed.get(node["name"])
        fill = "#d4edda" if ex else "#f8f9fa"
        stroke = "#1e7e34" if ex else "#adb5bd"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + box_w // 2}" y="{y + 22}" text-anchor="middle" font-size="13" '
            f'font-weight="bold">{node["label"]}</text>'
        )
        if ex:
            parts.append(
                f'<text x="{x + box_w // 2}" y="{y + 40}" text-anchor="middle" font-size="11" '
                f'fill="#1e7e34">{ex.get("duration_ms", 0):.1f} ms · {ex.get("status", "")}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)
