# agent_core → LangGraph 迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自研 agent_core 整体重写为基于 LangGraph 的图编排架构，技能以子图形式保留插件扫描，UI 统一通过 Agent 超级图驱动。

**Architecture:** 一个 Agent 超级图（入口 router 节点 + 各技能子图）。email 技能子图 fetch→classify。工具调用统一经 `safety.safe_call` 权限包裹。MemorySaver checkpointer 替代 memory.py。UI（main.py / ui_page.py）改为 invoke 超级图。

**Tech Stack:** Python 3.12（conda `GM-Assistant`）、langgraph（含 langchain-core）、streamlit 1.61、litellm、pytest（新增 dev 依赖）。

## Global Constraints

- **git 提交由用户自己处理**：本计划所有任务不包含 commit 步骤，执行者不要执行任何 git 提交/暂存操作。
- **测试必须强制 Mock 模式**：任何测试不得触发真实 IMAP 拉取或真实 LLM 调用。统一使用 `tests/conftest.py` 的 `mock_env` fixture。
- **命令执行**：Windows + Git Bash。Python 一律用 `D:\conda_envs\GM-Assistant\python.exe`，**禁止 `conda run`**（GBK 编码 bug）。
- 测试运行：`cd C:\intern\GM-Assistant && D:\conda_envs\GM-Assistant\python.exe -m pytest tests/ -v`（`python -m` 确保项目根目录在 sys.path）。
- 文件编码 UTF-8；中文注释符合项目现有风格；`# -*- coding: utf-8 -*-` 文件头保留。
- `langgraph` 版本约束：`>=0.3`（StateGraph / add_node / add_conditional_edges / compile(checkpointer=) 均为稳定 API）。
- 安全红线不变：`write_external` 在 `ENABLE_WRITE_EXTERNAL=false` 时必须被拒绝。

---

## File Structure

创建：
- `agent_core/state.py` —— `AgentState` TypedDict（新增）
- `agent_core/graph.py` —— `build_agent_graph()` + 全局单例 `agent`（新增）
- `skills/email/graph.py` —— email 子图节点函数与构建（新增）
- `tests/conftest.py` —— `mock_env` fixture（新增）
- `tests/test_state.py` / `test_safety.py` / `test_email_graph.py` / `test_orchestrator.py` / `test_graph.py` / `test_pages.py`（新增）
- `requirements-dev.txt` —— pytest（新增）

修改：
- `requirements.txt` —— 增加 `langgraph>=0.3`
- `agent_core/safety.py` —— 增加 `safe_call` / 异常类
- `agent_core/orchestrator.py` —— `SkillInfo` 增加 `routes`/`subgraph`；`_load_skill` 构建子图；新增 `route_map()`
- `skills/email/skill_manifest.py` —— 增加 `ROUTES` 与 `build_subgraph()`
- `skills/email/ui_page.py` —— `_refresh()` 改 invoke 超级图
- `main.py` —— 移除 `memory` 依赖，指标改读 checkpointer

删除：
- `agent_core/memory.py`（废弃，由 checkpointer 替代）

---

### Task 1: 依赖与测试基座 + AgentState

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `agent_core/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `agent_core.state.AgentState`（`TypedDict, total=False`，字段 `route/request/emails/classified/messages/errors`）；`tests/conftest.py::mock_env` fixture（monkeypatch config 强制 Mock）。

- [ ] **Step 1: 安装依赖**

```bash
cd C:/intern/GM-Assistant
"D:/conda_envs/GM-Assistant/python.exe" -m pip install langgraph
"D:/conda_envs/GM-Assistant/python.exe" -m pip install pytest
```

验证：`python -c "import langgraph; print(langgraph.__version__)"` 输出版本号。

- [ ] **Step 2: 修改 requirements.txt 与新增 requirements-dev.txt**

`requirements.txt` 末尾追加：
```
langgraph>=0.3
```

新增 `requirements-dev.txt`：
```
pytest>=8
```

- [ ] **Step 3: 创建 tests/conftest.py**

```python
# -*- coding: utf-8 -*-
"""pytest 公共 fixture：强制 Mock 模式，杜绝测试触发真实 IMAP/LLM。"""
import pytest

from config import config


@pytest.fixture
def mock_env(monkeypatch):
    """把全局 config 改为 Mock 模式（无真实邮箱、规则分类）。"""
    monkeypatch.setattr(config, "IMAP_SERVER", "")
    monkeypatch.setattr(config, "IMAP_EMAIL", "")
    monkeypatch.setattr(config, "IMAP_PASSWORD", "")
    monkeypatch.setattr(config, "LLM_MODE", "mock")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    return config
```

- [ ] **Step 4: 创建 agent_core/state.py**

```python
# -*- coding: utf-8 -*-
"""Agent 全局状态定义。

LangGraph 的 StateGraph 以 AgentState 作为节点间传递的状态 schema。
节点只读自己依赖的字段、写入自己的输出字段，共享同一份 state。
"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    route: str                  # router 选择的路径（如 refresh_email）
    request: dict[str, Any]     # 请求参数
    emails: list[dict]          # 拉取结果
    classified: list[dict]      # 分类结果
    messages: list[dict]        # 会话历史（替代原 memory.py）
    errors: list[str]           # 错误收集

    # Phase 2 追加：summaries / drafts / confirm_queue / sent_result
```

- [ ] **Step 5: 创建 tests/test_state.py（写失败测试）**

```python
# -*- coding: utf-8 -*-
from agent_core.state import AgentState


def test_agent_state_partial_fields():
    s = AgentState(route="refresh_email", emails=[], classified=[])
    assert s["route"] == "refresh_email"
    assert s.get("errors") is None  # total=False 允许缺省字段
```

- [ ] **Step 6: 运行测试确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_state.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'agent_core'` 或 import 错误（state.py 尚未创建）。

- [ ] **Step 7: 运行测试确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_state.py -v`
Expected: PASS（1 passed）。

---

### Task 2: 安全网关 safe_call

**Files:**
- Modify: `agent_core/safety.py`
- Test: `tests/test_safety.py`

**Interfaces:**
- Consumes: `agent_core.tool_registry.registry`、`gateway.check_permission`、`PERMIT_DENIED/PERMIT_NEEDS_CONFIRM`。
- Produces: `agent_core.safety.safe_call(tool_name: str, **kwargs) -> Any`；异常 `PermissionDeniedError`、`NeedsConfirmError`。

- [ ] **Step 1: 写失败测试 tests/test_safety.py**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_safety.py -v`
Expected: FAIL，`ImportError: cannot import name 'safe_call'`。

- [ ] **Step 3: 修改 agent_core/safety.py**

在文件末尾追加（保留现有 `gateway = SafetyGateway()` 单例）：

```python
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
```

（`registry`、`gateway`、`PERMIT_*` 常量已在文件顶部导入/定义，无需重复。）

- [ ] **Step 4: 运行确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_safety.py -v`
Expected: PASS（5 passed）。

---

### Task 3: email 技能子图 + manifest 升级

**Files:**
- Create: `skills/email/graph.py`
- Modify: `skills/email/skill_manifest.py`
- Test: `tests/test_email_graph.py`

**Interfaces:**
- Consumes: `agent_core.state.AgentState`、`agent_core.safety.safe_call`、`agent_core.logger.logger`。
- Produces: `skills.email.graph.build_email_subgraph()`（CompiledGraph，entry `fetch`）；`skills.email.skill_manifest.ROUTES = ["refresh_email"]`；`skills.email.skill_manifest.build_subgraph()`。

- [ ] **Step 1: 写失败测试 tests/test_email_graph.py**

```python
# -*- coding: utf-8 -*-
from skills.email.graph import build_email_subgraph
from skills.email.skill_manifest import ROUTES, build_subgraph


def test_manifest_exposes_route_and_subgraph(mock_env):
    assert "refresh_email" in ROUTES
    assert build_subgraph() is not None


def test_email_subgraph_refresh_flow(mock_env):
    graph = build_email_subgraph()
    result = graph.invoke({"route": "refresh_email"})
    assert result["emails"]            # Mock 8 封
    assert len(result["classified"]) == len(result["emails"])
```

- [ ] **Step 2: 运行确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_email_graph.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'skills.email.graph'`。

- [ ] **Step 3: 创建 skills/email/graph.py**

```python
# -*- coding: utf-8 -*-
"""email 技能子图：fetch → classify。

由 skill_manifest.build_subgraph() 返回，orchestrator 装配到 Agent 超级图。
节点统一经 safety.safe_call 调用工具，异常进 state["errors"]，不崩图。
"""
from langgraph.graph import END, StateGraph

from agent_core.logger import logger
from agent_core.safety import safe_call
from agent_core.state import AgentState


def fetch_node(state: AgentState) -> dict:
    try:
        emails = safe_call("fetch_emails")
        logger.info("email.graph", f"拉取 {len(emails)} 封邮件")
        return {"emails": emails}
    except Exception as e:
        logger.error("email.graph", f"拉取失败: {e}")
        return {"emails": [], "errors": [f"拉取失败: {e}"]}


def classify_node(state: AgentState) -> dict:
    emails = state.get("emails") or []
    try:
        classified = safe_call("classify_emails", emails=emails)
        logger.info("email.graph", f"分类完成 {len(classified)} 封")
        return {"classified": classified}
    except Exception as e:
        logger.error("email.graph", f"分类失败: {e}")
        return {"classified": [], "errors": [f"分类失败: {e}"]}


def build_email_subgraph():
    g = StateGraph(AgentState)
    g.add_node("fetch", fetch_node)
    g.add_node("classify", classify_node)
    g.set_entry_point("fetch")
    g.add_edge("fetch", "classify")
    g.add_edge("classify", END)
    return g.compile()
```

- [ ] **Step 4: 修改 skills/email/skill_manifest.py**

在文件顶部注释下、`get_tools()` 前新增：

```python
# 本技能子图可处理的 route 名（orchestrator 据此构建超级图路由表）
ROUTES = ["refresh_email"]


def build_subgraph():
    """构建并返回本技能子图；由 orchestrator 装配到 Agent 超级图。"""
    from skills.email.graph import build_email_subgraph

    return build_email_subgraph()
```

保留 `SKILL_META`、`get_tools()`、`get_status()`、`get_config_hint()` 不变。

- [ ] **Step 5: 运行确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_email_graph.py -v`
Expected: PASS（2 passed）。

---

### Task 4: orchestrator 改造（扫描构建子图 + 路由表）

**Files:**
- Modify: `agent_core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `skills.email.skill_manifest.ROUTES` / `build_subgraph`（动态导入）。
- Produces: `SkillInfo.routes: list[str]`、`SkillInfo.subgraph`；`Orchestrator.route_map() -> dict[str, str]`（route 名 → 技能节点名）。

- [ ] **Step 1: 写失败测试 tests/test_orchestrator.py**

```python
# -*- coding: utf-8 -*-
from agent_core.orchestrator import orchestrator


def test_scan_builds_email_subgraph(mock_env):
    skills = orchestrator.scan()
    email = next(s for s in skills if s.name == "email")
    assert email.status == "active"
    assert email.subgraph is not None
    assert "refresh_email" in email.routes


def test_route_map_maps_refresh_email(mock_env):
    orchestrator.scan()
    assert orchestrator.route_map()["refresh_email"] == "email"
```

- [ ] **Step 2: 运行确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_orchestrator.py -v`
Expected: FAIL，`AttributeError: 'SkillInfo' object has no attribute 'subgraph'`（或 route_map 不存在）。

- [ ] **Step 3: 修改 agent_core/orchestrator.py**

3a. `SkillInfo` dataclass 增加两字段（在 `hint`/`error` 之间）：

```python
    routes: list[str] = field(default_factory=list)  # 本技能子图可处理的 route
    subgraph: object | None = None                   # 编译后的 LangGraph 子图
```

3b. `_load_skill` 中，在 `info.hint = ...` 之后、`logger.info(...加载成功...)` 之前插入：

```python
            routes = getattr(module, "ROUTES", [])
            info.routes = list(routes)

            build_subgraph = getattr(module, "build_subgraph", None)
            if callable(build_subgraph):
                info.subgraph = build_subgraph()
```

3c. 在 `get_all_skills()` 之后新增方法：

```python
    def route_map(self) -> dict[str, str]:
        """返回 {route 名: 技能节点名} 映射，供超级图路由表使用。"""
        return {
            route: skill.name
            for skill in self._skills
            for route in skill.routes
        }
```

- [ ] **Step 4: 运行确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_orchestrator.py -v`
Expected: PASS（2 passed）。

---

### Task 5: Agent 超级图 graph.py

**Files:**
- Create: `agent_core/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `orchestrator.get_all_skills()`、`orchestrator.route_map()`、`AgentState`。
- Produces: `agent_core.graph.build_agent_graph()`（CompiledGraph，entry `route`，带 MemorySaver checkpointer）；全局单例 `agent`。

- [ ] **Step 1: 写失败测试 tests/test_graph.py**

```python
# -*- coding: utf-8 -*-
from agent_core.graph import agent


def test_agent_refresh_email_flow(mock_env):
    result = agent.invoke(
        {"route": "refresh_email"},
        config={"configurable": {"thread_id": "test-refresh"}},
    )
    assert result["route"] == "refresh_email"
    assert result["emails"]
    assert len(result["classified"]) == len(result["emails"])
    assert "errors" not in result


def test_agent_unknown_route_ends(mock_env):
    result = agent.invoke(
        {"route": "nonsense"},
        config={"configurable": {"thread_id": "test-unknown"}},
    )
    assert "classified" not in result
```

- [ ] **Step 2: 运行确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_graph.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'agent_core.graph'`。

- [ ] **Step 3: 创建 agent_core/graph.py**

```python
# -*- coding: utf-8 -*-
"""Agent 超级图：入口 router 节点 + 各技能子图。

build_agent_graph() 装配超级图并编译；agent 为全局单例。
UI 统一通过 agent.invoke({"route": ...}) 驱动，不再直接调用工具。
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent_core.logger import logger
from agent_core.orchestrator import orchestrator
from agent_core.state import AgentState


def route_node(state: AgentState) -> dict:
    """入口节点：记录路由并原样透传 state（实际分发在条件边完成）。"""
    route = state.get("route") or "unknown"
    logger.info("agent.graph", f"路由分发: {route}")
    return {}


def route_path(state: AgentState):
    """根据 route 决定进入哪个技能子图；未知 route 直接结束。"""
    return orchestrator.route_map().get(state.get("route"), END)


def build_agent_graph():
    g = StateGraph(AgentState)
    g.add_node("route", route_node)

    route_map = {}
    for skill in orchestrator.get_all_skills():
        if skill.subgraph is not None:
            g.add_node(skill.name, skill.subgraph)
            route_map[skill.name] = skill.name

    path_map = {**route_map, END: END}
    g.add_conditional_edges("route", route_path, path_map)
    g.set_entry_point("route")
    return g.compile(checkpointer=MemorySaver())


# 全局单例（进程启动时扫描并装配）
agent = build_agent_graph()
```

- [ ] **Step 4: 运行确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_graph.py -v`
Expected: PASS（2 passed）。

---

### Task 6: UI 接入图（ui_page + main）

**Files:**
- Modify: `skills/email/ui_page.py`（`_refresh()`）
- Modify: `main.py`（移除 memory 依赖）
- Test: `tests/test_pages.py`（AppTest）

**Interfaces:**
- Consumes: `agent_core.graph.agent`。
- Produces: UI 渲染不再直接调用工具；`main.py` 指标改读 checkpointer。

- [ ] **Step 1: 写失败测试 tests/test_pages.py**

```python
# -*- coding: utf-8 -*-
from streamlit.testing.v1 import AppTest


def test_email_page_refresh_renders_groups(mock_env):
    at = AppTest.from_file("pages/01_邮件处理.py", default_timeout=30)
    at.run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception
    assert len(at.expander) >= 1  # 至少渲染出邮件展开器


def test_overview_page_renders(mock_env):
    at = AppTest.from_file("main.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.metric) >= 3    # 技能模块 / 工具注册 / 安全模式
```

- [ ] **Step 2: 运行确认失败**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_pages.py -v`
Expected: 当前行为下 `test_email_page_refresh_renders_groups` 仍可能通过（旧代码直接调工具也 OK），`test_overview_page_renders` 通过。若已通过，改为「回归基线」——先跑一遍记录现状，确保改动后仍通过。

- [ ] **Step 3: 修改 skills/email/ui_page.py 的 _refresh()**

替换原 `_refresh()` 函数体：

```python
def _refresh() -> None:
    """触发 Agent 超级图执行「刷新邮件」路径。"""
    from agent_core.graph import agent

    with st.spinner("正在拉取并分类邮件..."):
        try:
            result = agent.invoke(
                {"route": "refresh_email"},
                config={"configurable": {"thread_id": "ui"}},
            )
            classified = result.get("classified") or []
            st.session_state[_KEY_EMAILS] = classified
            st.session_state[_KEY_LAST_REFRESH] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state[_KEY_LAST_COUNT] = len(classified)
            logger.info("email.ui_page", f"刷新完成，共 {len(classified)} 封邮件")
            for err in result.get("errors") or []:
                st.warning(err)
        except Exception as e:
            logger.error("email.ui_page", f"刷新失败: {e}")
            st.error(f"刷新失败：{e}")
    st.rerun()
```

同时删除文件顶部不再使用的 import：`from skills.email.email_classifier import classify_emails` 与 `from skills.email.mail_fetcher import fetch_emails`（若删除后无其他引用）。

- [ ] **Step 4: 修改 main.py**

4a. 删除 import 行：`from agent_core.memory import memory`。

4b. 替换「会话消息」指标取值逻辑。原：

```python
c4.metric("会话消息", len(memory))
```

改为：

```python
from agent_core.graph import agent  # 顶部 import 区追加

# ...顶部指标区...
try:
    _snap = agent.get_state({"configurable": {"thread_id": "ui"}})
    _msg_count = len(_snap.values.get("messages") or []) if _snap else 0
except Exception:
    _msg_count = 0
c4.metric("会话消息", _msg_count)
```

- [ ] **Step 5: 运行确认通过**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/test_pages.py -v`
Expected: PASS（2 passed），且无回归。

---

### Task 7: memory.py 废弃与清理 + 回归

**Files:**
- Delete: `agent_core/memory.py`
- Verify: 全库无残留 import

**Interfaces:**
- Consumes: 全库 import 检查。
- Produces: `agent_core/` 不再有 memory 模块。

- [ ] **Step 1: 搜索残留引用**

Run: `grep -rn "agent_core.memory\|from agent_core import memory\|import memory" agent_core/ skills/ main.py pages/`
Expected: 无输出（若 Task 6 已移除 main.py 引用）。若还有残留，先清理对应 import。

- [ ] **Step 2: 删除 memory.py**

```bash
rm "C:/intern/GM-Assistant/agent_core/memory.py"
```

- [ ] **Step 3: 全量回归**

Run: `"D:/conda_envs/GM-Assistant/python.exe" -m pytest tests/ -v`
Expected: 全部 PASS（state 1 + safety 5 + email_graph 2 + orchestrator 2 + graph 2 + pages 2 = 14 passed）。

- [ ] **Step 4: 真实模式回归（手动，不进入自动测试）**

```bash
cd C:/intern/GM-Assistant
"D:/conda_envs/GM-Assistant/python.exe" -c "from agent_core.graph import agent; r = agent.invoke({'route':'refresh_email'}, config={'configurable':{'thread_id':'real-check'}}); print('emails:', len(r.get('emails', [])), 'classified:', len(r.get('classified', [])))"
```

Expected: 输出 `emails: N, classified: N`（N>0，使用真实 .env 拉取 + LLM 分类）。

- [ ] **Step 5: 更新 README 架构说明**

在 `README.md` 第 2 节「平台骨架」补充一句：

> 编排层基于 **LangGraph**：Agent 超级图（Router 入口 + 技能子图），工具调用统一经安全网关 `safe_call` 包裹；技能=子图，由 orchestrator 扫描 `skill_manifest` 装配。

---

## Self-Review

**Spec coverage：**
- §4 组件映射 → Task 1-7 全部覆盖（state/orchestrator/safety/graph/manifest/ui/memory/依赖）。
- §6 插件契约（build_subgraph + ROUTES）→ Task 3、4。
- §7 safe_call + 权限红线 → Task 2。
- §8 数据流（router → email 子图）→ Task 3、5。
- §9 错误处理（节点异常进 errors，不崩图）→ Task 3 节点实现 + Task 6 UI 展示 errors。
- §10 测试 → Task 1-6 测试 + Task 7 回归。
- §11 依赖 langgraph → Task 1。

**Placeholder scan：** 无 TBD/TODO；所有步骤含具体代码与命令。

**Type consistency：** `safe_call(tool_name, **kwargs)` 在 Task 2 定义、Task 3 节点调用；`build_subgraph()`/`ROUTES` 在 Task 3 定义、Task 4 读取；`route_map()` 在 Task 4 定义、Task 5 使用；`agent` 单例在 Task 5 定义、Task 6 使用 —— 签名一致。
