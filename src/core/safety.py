# -*- coding: utf-8 -*-
"""安全网关。

管理操作权限白名单：
- read：默认放行
- write_internal：需用户在 UI 中确认
- write_external：默认禁用，需配置文件显式开启（对应安全红线）
"""
from src.core.config_manager import config
from src.core.tool_registry import registry, TOOL_READ, TOOL_WRITE_EXTERNAL, TOOL_WRITE_INTERNAL

# 权限判定结果
PERMIT_ALLOWED = "allowed"
PERMIT_NEEDS_CONFIRM = "needs_confirm"
PERMIT_DENIED = "denied"
PERMIT_UNKNOWN = "unknown"


class SafetyGateway:
    """根据工具类型与全局配置判定操作是否允许。"""

    def __init__(self, allow_write_external: bool | None = None) -> None:
        # 外部写是否开启；默认读取全局配置
        self._allow_write_external = (
            config.ENABLE_WRITE_EXTERNAL if allow_write_external is None else allow_write_external
        )

    @property
    def allow_write_external(self) -> bool:
        return self._allow_write_external

    def check_permission(self, tool_name: str) -> str:
        """返回权限判定结果：allowed / needs_confirm / denied / unknown。"""
        definition = registry.get_tool(tool_name)
        if definition is None:
            return PERMIT_UNKNOWN
        if definition.tool_type == TOOL_READ:
            return PERMIT_ALLOWED
        if definition.tool_type == TOOL_WRITE_INTERNAL:
            return PERMIT_NEEDS_CONFIRM
        if definition.tool_type == TOOL_WRITE_EXTERNAL:
            return PERMIT_ALLOWED if self._allow_write_external else PERMIT_DENIED
        return PERMIT_DENIED

    def mode(self) -> str:
        """安全模式：strict（外部写禁用）/ relaxed（外部写开启）。"""
        return "relaxed" if self._allow_write_external else "strict"


# 全局单例
gateway = SafetyGateway()


from typing import Any


class PermissionDeniedError(Exception):
    """工具被安全网关拒绝（未注册 / 外部写被禁用）。"""


class NeedsConfirmError(Exception):
    """write_internal 工具需要用户确认。"""


def safe_call(tool_name: str, **kwargs: Any) -> Any:
    """经权限判定后执行工具 handler。

    - read：放行
    - write_internal：抛 NeedsConfirmError（调用方负责 UI 确认 / Phase 2 用 interrupt）
    - write_external：ENABLE_WRITE_EXTERNAL=false 时抛 PermissionDeniedError
    - 未注册工具：抛 PermissionDeniedError
    """
    definition = registry.get_tool(tool_name)
    if definition is None:
        raise PermissionDeniedError(f"未注册工具: {tool_name}")
    verdict = gateway.check_permission(tool_name)
    if verdict == PERMIT_DENIED:
        raise PermissionDeniedError(f"工具被安全网关拒绝: {tool_name}")
    if verdict == PERMIT_NEEDS_CONFIRM:
        raise NeedsConfirmError(f"工具需要用户确认: {tool_name}")
    return definition.handler(**kwargs)
