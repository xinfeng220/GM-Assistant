# -*- coding: utf-8 -*-
from src.core.visualizer import render_graph_svg

NODES = [
    {"name": "route", "label": "route"},
    {"name": "fetch_node", "label": "email.fetch"},
    {"name": "classify_node", "label": "email.classify"},
]
EDGES = [("route", "fetch_node"), ("fetch_node", "classify_node")]


def test_default_svg_width_matches_historical():
    svg = render_graph_svg(NODES, EDGES)
    assert 'width="610"' in svg   # margin*2 + 3*box_w + 2*gap_x = 40 + 450 + 120
    assert "<rect" in svg


def test_compact_params_produce_narrow_svg():
    svg = render_graph_svg(
        NODES, EDGES,
        box_w=96, box_h=46, gap_x=22, gap_y=32, margin=14,
        font_size=11, font_size_sub=9,
    )
    assert 'width="360"' in svg   # 28 + 3*96 + 2*22
    assert "<rect" in svg


def test_executed_node_highlighted():
    executed = {"fetch_node": {"duration_ms": 12.5, "status": "ok"}}
    svg = render_graph_svg(NODES, EDGES, executed)
    assert 'stroke="#1e7e34"' in svg
    assert "12.5 ms" in svg
