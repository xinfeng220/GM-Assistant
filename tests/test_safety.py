# -*- coding: utf-8 -*-
import pytest

from agent_core.safety import (
    PermissionDeniedError,
    NeedsConfirmError,
    safe_call,
)
from agent_core.tool_registry import (
    TOOL_READ,
    TOOL_WRITE_EXTERNAL,
    TOOL_WRITE_INTERNAL,
    ToolDefinition,
    registry,
)


def _register(name: str, tool_type: str, handler) -> None:
    registry.register_tool(
        ToolDefinition(name=name, tool_type=tool_type, module="test", handler=handler)
    )


def test_safe_call_read_allowed():
    _register("t_read", TOOL_READ, lambda: "ok")
    assert safe_call("t_read") == "ok"


def test_safe_call_read_passes_kwargs():
    _register("t_echo", TOOL_READ, lambda x: x)
    assert safe_call("t_echo", x=42) == 42


def test_safe_call_write_external_denied():
    _register("t_send", TOOL_WRITE_EXTERNAL, lambda: "sent")
    with pytest.raises(PermissionDeniedError):
        safe_call("t_send")


def test_safe_call_write_internal_raises_confirm():
    _register("t_draft", TOOL_WRITE_INTERNAL, lambda: "draft")
    with pytest.raises(NeedsConfirmError):
        safe_call("t_draft")


def test_safe_call_unknown_tool():
    with pytest.raises(PermissionDeniedError):
        safe_call("t_never_registered")
