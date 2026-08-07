# GM-Assistant：agent_core → LangGraph 迁移设计

- **日期**：2026-08-07
- **状态**：已确认（用户批准）
- **范围**：将自研 agent_core 框架整体重写为基于 LangGraph 的图编排架构

---

## 1. 背景与动机

当前 `agent_core/` 是自研的轻量技能插件框架（orchestrator 扫描 skills/ 注册工具、tool_registry、safety、logger、memory）。Phase 1 中它只承担了最简单的编排（UI 直接调用 `fetch_emails` → `classify_emails` 两个工具），没有任何 agent 循环。

后续 Phase 2+ 将引入多步骤流程：摘要 → 草拟 → **人工确认** → 发送，以及需求文档 2.1 规划的 **Router + Tool-use Loop** 交互模式。这些是多步、有状态、需要 human-in-the-loop 的工作流，正是 LangGraph 的适用场景。

**决策**：整个 agent_core 重写为 LangGraph；技能以子图形态保留插件扫描机制；采用一个 Agent 超级图（Router 入口 + 技能子图）的边界结构。

## 2. 目标

- 用 LangGraph 统一承载所有流程编排（批处理流水线、未来的 Router + Tool-use Loop）
- 保留并升级技能插件机制：新技能 = 新子图，加技能不改核心装配代码
- 工具注册、安全网关融入 graph 调用链，安全红线（AI 绝不自动外发）不因重构而削弱
- Phase 1 现有功能（邮件拉取 + 分类 + UI 展示）在迁移后行为不变

## 3. 总体架构

```
用户层（Streamlit UI）                 —— UI 改为 invoke 图，不再直接调工具
   │  agent.invoke({"route": ...}, config={"configurable": {"thread_id": ...}})
   ▼
Agent 超级图（agent_core/graph.py）    —— 入口 router 节点分发
   │
   ├── 技能子图 A（email）：fetch → classify → END
   │      （Phase 2：+ summarize → draft → human-confirm → send）
   ├── 技能子图 B（未来技能）……
   │
   工具调用一律经 safe_call（安全网关包裹）
基础设施：tool_registry（保留）· safety（保留，融入调用链）· logger（保留）
持久化：LangGraph MemorySaver（内存 checkpointer）替代 memory.py
```

## 4. 组件映射

| 现文件 | 处理 | LangGraph 形态 |
| :--- | :--- | :--- |
| `agent_core/orchestrator.py` | 改造 | 扫描 `skills/`，用 manifest 构建技能**子图**并装配到超级图 |
| `agent_core/tool_registry.py` | 保留 | `ToolDefinition` 元数据 + handler 注册中心（子图节点经它获取 handler） |
| `agent_core/safety.py` | 保留改造 | 新增 `safe_call(tool_name, **kwargs)`：先 `check_permission` 再执行 handler；`write_external` 达发送节点时用 LangGraph `interrupt()` 做人工确认（Phase 2 用） |
| `agent_core/logger.py` | 保留 | 不变 |
| `agent_core/memory.py` | 废弃 | 由 LangGraph State 的 `messages` 字段 + MemorySaver checkpointer 替代 |
| `skills/email/skill_manifest.py` | 升级 | 新增 `build_subgraph()` 声明子图（fetch→classify）；`get_tools()`/`get_status()`/`get_config_hint()` 保留 |
| `main.py` | 改造 | 总览页改从 graph/checkpointer 读技能状态与消息计数 |
| `skills/email/ui_page.py` | 改造 | 改为 invoke 超级图，从返回的 state 渲染 |

新增文件：
- `agent_core/state.py` —— `AgentState` TypedDict
- `agent_core/graph.py` —— `build_agent_graph()` 装配超级图，返回 CompiledGraph；全局单例 `agent`
- `skills/email/graph.py` —— email 技能子图构建（节点函数 + 连线）

## 5. State 定义（`agent_core/state.py`）

```python
from typing import TypedDict, Any

class AgentState(TypedDict, total=False):
    route: str              # router 选择的路径：refresh_email / ...
    request: dict[str, Any] # 请求参数
    emails: list[dict]      # 拉取结果
    classified: list[dict]  # 分类结果
    messages: list[dict]    # 会话历史（替代 memory.py）
    errors: list[str]       # 错误收集
    # Phase 2 追加：summaries / drafts / confirm_queue / sent_result
```

State 由各节点增量填充，节点只读自己依赖的字段，写入自己的输出字段。

## 6. 技能插件机制（升级后）

`skills/<name>/skill_manifest.py` 契约：

```python
SKILL_META = {"name", "title", "description", "version"}

def build_subgraph() -> CompiledSubgraph | None:
    """声明本技能的子图（由 orchestrator 装配到超级图）。"""
    # 可选：无独立子图、仅提供工具的技能可返回 None

def get_tools() -> list[ToolDefinition]: ...   # 保留：声明工具元数据（供安全网关/总览）
def get_status() -> str: ...                    # 保留
def get_config_hint() -> str: ...               # 保留
```

Orchestrator 职责变化：
1. 扫描 `skills/*/skill_manifest.py`
2. 调用 `build_subgraph()` 得到子图，装配进超级图的对应路径
3. 单技能构建失败 → 标记 status=error，不阻塞其他技能（沿用现有隔离思路）

## 7. 安全网关融入调用链

`agent_core/safety.py` 新增：

```python
def safe_call(tool_name: str, **kwargs) -> Any:
    """经权限判定后执行工具 handler。"""
    definition = registry.get_tool(tool_name)
    if definition is None:
        raise PermissionError(f"未注册工具: {tool_name}")
    verdict = gateway.check_permission(tool_name)
    if verdict == PERMIT_DENIED:
        raise PermissionError(f"工具被安全网关拒绝: {tool_name}")
    if verdict == PERMIT_NEEDS_CONFIRM:
        # write_internal：调用方（节点）负责走 UI 确认 / interrupt（Phase 2 用）
        raise NeedsConfirmError(tool_name)
    return definition.handler(**kwargs)
```

- 子图节点内部统一调用 `safe_call`，不在节点里直接碰 handler
- `write_external`（发送）工具在 `ENABLE_WRITE_EXTERNAL=false` 时被拒，保持安全红线
- Phase 2 发送节点用 LangGraph `interrupt()` 暂停图，等人工确认后继续（本设计只预留，不实现）

## 8. 数据流（当前唯一路径：刷新邮件）

```
invoke({route: "refresh_email"})
→ router 节点：route == "refresh_email" → 进 email 子图
→ fetch 节点：safe_call("fetch_emails") → state["emails"]
→ classify 节点：safe_call("classify_emails", emails) → state["classified"]
→ END 返回 state
UI 读 state["classified"] 按紧急度分组渲染
```

Router 节点当前为配置/硬编码分发；Phase 2 起演化为 LLM 意图路由（需求文档 2.1）。

## 9. 错误处理

- **节点内工具异常**：捕获 → `logger.error` → 追加到 `state["errors"]`，图正常结束，UI 展示错误，不崩进程
- **权限 denied**：`safe_call` 抛 `PermissionError`，节点捕获后进 `errors`，该路径短路
- **LLM 分类失败**：沿用分类器现有「退回规则分类」兜底，行为不变
- **单技能子图构建失败**：status=error，其余技能照常装配

## 10. 测试

1. **冒烟**：`build_agent_graph()` 成功；`agent.invoke({"route": "refresh_email"})` 返回带分类结果的 state
2. **权限**：`safe_call("fetch_emails")` 放行；`safe_call("send_email")`（若注册）被拒；未注册工具 → 拒绝
3. **AppTest**：`main.py` 总览页 + `01_邮件处理.py` 经 graph 后渲染正常（指标：技能 1 / 工具 2 / 安全模式 strict）
4. **回归**：Mock 模式（无 .env）下 8 封样例流程与迁移前一致

## 11. 依赖

- `requirements.txt` 增加 `langgraph`（自动依赖 langchain-core）
- 安装命令：`D:\conda_envs\GM-Assistant\python.exe -m pip install langgraph`

## 12. 本次不做（后续 Phase）

- 摘要 / 草拟 / 发送节点与子图扩展
- LLM 意图路由（Router 演进）
- 草稿确认队列、`interrupt()` 人工确认落地
- 多邮箱、团队协作
- 持久化 checkpointer（Postgres/SQLite）—— 本次用内存 MemorySaver
