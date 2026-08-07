# -*- coding: utf-8 -*-
"""统一工具注册中心。

集中注册/查询各技能通过 skill_manifest.py 声明的工具，并区分工具读写类型，
供安全网关（safety.py）做权限判定。
"""
from dataclasses import dataclass, field
from typing import Callable

# 工具类型
TOOL_READ = "read"                      # 读操作：默认放行
TOOL_WRITE_INTERNAL = "write_internal"  # 内部写（如存草稿）：需用户确认
TOOL_WRITE_EXTERNAL = "write_external"  # 外部写（如发送）：默认禁用
TOOL_TYPES = (TOOL_READ, TOOL_WRITE_INTERNAL, TOOL_WRITE_EXTERNAL)


@dataclass
class ToolDefinition:
    """单个工具的定义描述。"""

    name: str
    tool_type: str
    module: str                      # 归属的技能模块名
    description: str = ""
    handler: Callable | None = None  # 实际执行函数
    requires_config: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tool_type not in TOOL_TYPES:
            raise ValueError(f"非法工具类型: {self.tool_type}，允许值: {TOOL_TYPES}")


class ToolRegistry:
    """工具字典：{tool_name: ToolDefinition}。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(self, definition: ToolDefinition) -> None:
        """注册工具（同名工具后注册者覆盖）。"""
        self._tools[definition.name] = definition

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_all(self) -> dict[str, ToolDefinition]:
        return dict(self._tools)

    def count(self) -> int:
        return len(self._tools)

    def list_by_module(self, module: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.module == module]

    def clear(self) -> None:
        self._tools.clear()


# 全局单例
registry = ToolRegistry()
