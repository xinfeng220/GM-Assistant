# -*- coding: utf-8 -*-
from src.core import ui


def test_default_graph_constants_shape():
    names = {n["name"] for n in ui._DEFAULT_NODES}
    assert names == {"route", "fetch_node", "classify_node"}
    for node in ui._DEFAULT_NODES:
        assert "name" in node and "label" in node
    for src, dst in ui._DEFAULT_EDGES:
        assert src in names and dst in names
