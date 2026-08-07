# 后端结构化重构设计（Backend Restructure Design）

> **日期**：2026-08-07
> **状态**：已获用户批准（v1）

## 1. 背景与目标

当前 GM-Assistant 架构（agent_core 核心 + skills 技能插件）已能跑通 Phase 1 最小闭环，但存在拓展性摩擦：技能契约隐式、数据全裸 dict、config 单一扁平类、LLM 调用分散、route 无命名空间、无观测。

本次重构以 `gaokao_tutor` 项目架构为**模式参考**（仅借鉴，不并入），将 GM-Assistant 改造为**能力平台形态**：email 只是 `src/capabilities/` 下的第一个能力，后续可挂载更多能力（gaokao 辅导、日程、搜索等）。

**目标**：
1. 代码更结构化：类型化模型、配置外置、LLM 统一、能力模块自包含。
2. 拓展性强：加一个新能力不改核心运行时，契约有校验、route 不撞名。
3. 可观测可视化：图执行轨迹、工具审计、token 指标在 Streamlit 可见。

## 2. 决策基线（用户确认）

| 决策 | 结论 |
| :--- | :--- |
| 前端栈 | **保留 Streamlit**，新增图执行可视化（零依赖 SVG） |
| 平台归属 | gaokao_tutor 为独立仓库，**只借鉴模式**，不并 RAG 那套 |
| 节奏 | **先做后端结构化**，全程 16 tests 保持全绿 |
| 命名 | 接受改名：`agent_core/` → `src/core/`，`skills/` → `src/capabilities/`，`config.py` → `src/core/config_manager.py` |
| 可视化渲染 | 零依赖手写 SVG（`src/core/visualizer.py` + Streamlit `st.components.v1.html`） |
| 数据模型 | Pydantic（v2，随 langgraph 已安装） |
| git 提交 | 由用户自行处理（用户偏好），本次只产出文件 |

## 3. 目标目录结构

```
GM-Assistant/
├── main.py                        # Streamlit 总览页
├── pages/
│   ├── 01_可视化.py               # 新增：图结构 + 执行轨迹可视化
│   └── 02_邮件处理.py             # 薄转发 → src.capabilities.email.ui_page
├── config/
│   ├── settings.yaml              # 非敏感运行参数
│   └── prompts/
│       └── email/
│           ├── classification.txt # 原 skills/email/prompts/classification.py 内容外置
│           ├── summary.txt        # Phase 2 预留（空文件/占位说明）
│           └── draft.txt          # Phase 2 预留
├── src/
│   ├── __init__.py
│   ├── core/                      # 平台运行时（与具体能力无关）
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic：Email / Classification / EmailClassified
│   │   ├── config_manager.py      # settings.yaml + .env 覆盖 + prompt 模板缓存
│   │   ├── llm.py                 # LLM 工厂 + invoke_with_fallback
│   │   ├── state.py               # AgentState（共享通道 + capability 标记）
│   │   ├── router.py              # 路由解析（命名空间 route → Phase 2 LLM 意图）
│   │   ├── graph.py               # 超级图装配 + agent 单例
│   │   ├── orchestrator.py        # 能力扫描 + manifest 契约校验
│   │   ├── safety.py              # 安全网关 + safe_call（保留逻辑）
│   │   ├── tool_registry.py       # 工具注册中心（保留）
│   │   ├── checkpointer.py        # 会话持久化抽象（现 MemorySaver）
│   │   ├── tracing.py             # 执行轨迹 + 工具审计 + token 记录
│   │   ├── visualizer.py          # 图结构 SVG 渲染 + 执行轨迹标注
│   │   └── logger.py              # 统一日志/脱敏（保留）
│   ├── capabilities/
│   │   ├── __init__.py
│   │   └── email/
│   │       ├── __init__.py
│   │       ├── manifest.py        # 契约声明（原 skill_manifest.py）
│   │       ├── graph.py           # email 子图（fetch → classify）
│   │       ├── fetcher.py         # 原 mail_fetcher.py
│   │       ├── classifier.py      # 原 email_classifier.py（LLM 调用走 core.llm）
│   │       ├── tools.py           # 工具定义（fetch_emails / classify_emails）
│   │       └── ui_page.py         # Streamlit 页
│   └── tools/                     # 共享工具（后续，本轮只建包）
├── tests/                         # 现有 6 文件（改 import）+ 新增
├── docs/superpowers/              # 设计/计划文档
└── requirements*.txt              # 补 pydantic 显式声明（可选）
```

## 4. 各设计点规格

### 4.1 包结构与 import 迁移（纯机械，无行为变化）

| 旧 | 新 |
| :--- | :--- |
| `agent_core/` | `src/core/` |
| `skills/` | `src/capabilities/` |
| `config.py`（模块） | `src/core/config_manager.py`（Config 类保留） |
| `skills/email/skill_manifest.py` | `src/capabilities/email/manifest.py` |
| `skills/email/mail_fetcher.py` | `src/capabilities/email/fetcher.py` |
| `skills/email/email_classifier.py` | `src/capabilities/email/classifier.py` |
| `skills/email/prompts/` | `config/prompts/email/` |

项目根目录在 sys.path（pytest.ini `pythonpath = .`，streamlit 从根启动），`from src.core.graph import agent` 可解析。`src/`、`src/core/`、`src/capabilities/`、`src/capabilities/email/` 均有 `__init__.py`。

### 4.2 schemas.py（Pydantic 类型化）

```python
from pydantic import BaseModel, Field, field_validator

URGENCY_LEVELS = ("紧急", "重要", "普通", "可忽略")
ACTIONS = ("需要回复", "仅需阅读", "可转交", "可归档")

class Classification(BaseModel):
    urgency: str
    action: str
    category_tag: str = "其他"
    reason: str = ""
    confidence: float | None = None      # Phase 2 LLM 置信度

    @field_validator("urgency")
    @classmethod
    def _val_urgency(cls, v): ...        # 非法回退 "普通"（复用现有 _validate_result 语义）
    @field_validator("action")
    @classmethod
    def _val_action(cls, v): ...         # 非法回退 "仅需阅读"

class Email(BaseModel):
    id: str
    subject: str = ""
    from_: str = Field(default="", alias="from")   # 序列化/构造仍用 "from"
    received_at: str = ""
    body_preview: str = ""

    model_config = {"populate_by_name": True}

class EmailClassified(Email):
    classification: Classification
```

- `fetch_emails` 返回 `list[Email]`；`classify_emails` 返回 `list[EmailClassified]`。
- 现有 `_validate_result` 的归一化逻辑移入 `Classification` 的 field_validator。
- UI/节点访问从 `item.get("classification").get("urgency")` 改为 `item.classification.urgency`、`item.from_`。
- 序列化对外仍用 `"from"`（by_alias），兼容既有消费方。

### 4.3 config_manager.py（settings.yaml + .env 覆盖 + prompt 缓存）

`config/settings.yaml`（非敏感，默认值从代码迁入）：
```yaml
llm:
  mode: mock                 # mock / real
  model: deepseek/deepseek-chat
  base_url: ""
  temperature: 0.0
email:
  fetch_limit: 20
  body_preview_len: 300
safety:
  enable_write_external: false
tracing:
  enabled: true
  recent_maxlen: 200
```

规则：
- **密钥只在 .env**（IMAP_SERVER/IMAP_EMAIL/IMAP_PASSWORD、LLM_API_KEY），绝不进 yaml。
- 取值优先级：环境变量 > settings.yaml > 代码默认值。
- `Config` 类保留现有属性访问（`config.IMAP_SERVER`、`config.imap_configured`、`config.llm_configured`），conftest 的 `mock_env`（monkeypatch 属性）不需改动。
- `BASE_DIR` 指向项目根（`src/core/config_manager.py` 上溯三级），`.env` 与 `config/` 均从根解析。

prompt 模板：
- 模板文件在 `config/prompts/<能力>/<名>.txt`。
- `Config.get_prompt(name: str) -> str`：按 `能力.名` 查（如 `get_prompt("email.classification")`），读文件并**线程安全缓存**（lru_cache）。
- 原 `classification.py` 的 SYSTEM_PROMPT 内容原样写入 `config/prompts/email/classification.txt`。

### 4.4 llm.py（LLM 工厂 + 容灾）

```python
class LLMError(Exception): ...

def completion(messages: list[dict], *, model: str | None = None,
               temperature: float | None = None, **kwargs) -> str:
    """统一 litellm 调用；model/base_url/api_key 从 config_manager 取；
    成功后将 usage token 记录到 tracing。返回文本内容。"""

def invoke_with_fallback(primary, fallback, *, label: str = ""):
    """primary() 抛异常 → 记录 fallback 事件 → 返回 fallback(exc)；
    成功返回 primary() 结果。供分类/摘要等「LLM 优先、规则兜底」场景复用。"""
```

- 从 `config` 读 LLM_MODE/LLM_MODEL/LLM_BASE_URL/LLM_API_KEY；mock 模式不应调用本模块（由调用方判 `llm_configured`）。
- `classifier.classify_one` 中 `_llm_classify` 的 litellm 调用替换为 `core.llm.completion`；LLM→规则降级用 `invoke_with_fallback`。
- 删除 classifier 内的 `_parse_json`/`_llm_classify` 中重复的 litellm 封装（JSON 解析保留在 classifier 或迁入 llm 统一 `completion_json`，取其一；本设计选**保留在 classifier**，llm.py 只做传输）。

### 4.5 state.py + router.py（共享通道 + 命名空间 route）

```python
class AgentState(TypedDict, total=False):
    route: str            # 命名空间 route，如 "email.refresh"
    request: dict[str, Any]
    capability: str       # 本次执行的能力名（如 "email"）
    messages: list[dict]  # 会话历史（Phase 2 启用）
    errors: list[str]
    # email 能力输出（当前唯一能力，保持顶层；多能力时再引入 capabilities/<name> 命名空间）
    emails: list[Email]
    classified: list[EmailClassified]
```

- **route 命名空间化**：manifest 声明裸 route 名（`ROUTES = ["refresh"]`），orchestrator 以 `f"{skill.name}.{route}"` 前缀成 `email.refresh`。技能名唯一 → route 天然不撞名。
- `router.py`：
  ```python
  def resolve(route: str) -> str | None:
      """route_map().get(route)；找不到返回 None（超级图退化为 END）。"""
  def normalize(route: str) -> str:
      """兼容旧名（refresh_email → email.refresh）？——不提供，测试与 UI 一并更新。"""
  ```
  超级图 `route_path` 的 valid_targets 钳制保留（指向未装配能力的 route 退化 END，不崩图）。
- Phase 2：`resolve` 演进为 LLM 意图分类（Pydantic 结构化输出 Intent，对应参考 supervisor.py），接口保持 `resolve(request) -> route`。

### 4.6 orchestrator.py（能力扫描 + 契约校验）

- 扫描目录不变（`src/capabilities/*/manifest.py`），`SKILLS_DIR` 改指向新路径。
- 新增**契约校验**（每项失败 → `status="error"` + 明确 `error` 文案，不阻塞其他能力）：
  1. `SKILL_META` 存在且 `name` 为非空 str。
  2. `get_tools()` 返回可迭代且每个元素为 `ToolDefinition`（`tool_type` 合法性由 `ToolDefinition.__post_init__` 保证）。
  3. `ROUTES` 为 str 列表；**ROUTES 非空但 `build_subgraph` 不可调用 → error**「声明了 ROUTES 却缺 build_subgraph」。
  4. `build_subgraph()` 执行抛错 → error（现有行为）。
- `route_map()` 改为生成命名空间 key：`{f"{skill.name}.{route}": skill.name}`。
- `SkillInfo` 保留 routes/subgraph/tools/hint/error 字段（语义不变）。

### 4.7 checkpointer.py（持久化抽象）

```python
def build_checkpointer():
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
```
- `graph.py` 不再直接 import MemorySaver，改调 `build_checkpointer()`。
- 后续可替换为 Postgres checkpoint（对应参考 `src/database/checkpointer.py`），接口不变。

### 4.8 tracing.py + visualizer.py + 可视化页

`tracing.py`（进程内观测，结构化缓冲）：
```python
class TraceRecorder:
    def begin_run(self, route: str) -> str          # 返回 run_id
    def record_node(self, run_id, node, status, duration_ms, detail="")
    def record_tool(self, run_id, tool, status)
    def record_tokens(self, run_id, n)
    def record_fallback(self, run_id, label)
    def get_run(self, run_id) -> dict | None
    def get_last_run(self) -> dict | None
    def recent_runs(self, n: int) -> list[dict]

tracer = TraceRecorder()
```

- 节点包装：`src/core/tracing.py` 提供 `@traced` 装饰器，包裹子图节点函数（计时 + `record_node`），email/graph.py 节点注册时使用。
- 工具审计：`safe_call` 内记录 `record_tool(tool_name, status)`（对应需求文档 6.3 审计日志）。
- token：`llm.completion` 成功后 `record_tokens`。

`visualizer.py`（零依赖 SVG）：
```python
def render_graph_svg(nodes: list[dict], edges: list[tuple], executed: dict[str, dict]) -> str:
    """画有向无环图：节点为矩形盒、边为箭头；已执行节点绿色高亮并标耗时。返回 SVG 字符串。"""
```
- 图结构来源：本设计显式维护 email 子图结构与超级图结构的「节点+边」描述（email 子图 fetch→classify；超级图 route→email）。
- Streamlit 页经 `st.components.v1.html(svg, height=...)` 渲染。

`pages/01_可视化.py` 内容：
- 图结构 DAG（SVG，执行过的节点高亮）
- 最近一次执行轨迹表（`st.dataframe`：节点 / 状态 / 耗时 / 产出）
- token 与 LLM 调用指标（`st.metric`：最近运行次数、LLM 调用数、token 总数）
- 工具调用审计表（时间 / 工具 / 结果）
- 最近日志（`logger.recent(20)`）

`main.py` 总览页：把恒为 0 的「会话消息」指标替换为 tracing 的真实指标（最近执行次数 / LLM 调用 / token），或标注「Phase 2 启用」。

### 4.9 UI 能力注册

- `pages/02_邮件处理.py` 薄转发 `src.capabilities.email.ui_page.render()`（与现状一致，仅改 import 路径）。
- 总览页技能列表经 orchestrator 展示各能力状态（不变）。
- 新能力接入方式（写进文档/脚手架注释）：`src/capabilities/<name>/` 放 manifest + tools + graph + ui_page，`pages/` 加一行转发。

## 5. 测试策略

- 全程现有 16 tests 保持绿（conftest `mock_env` 强制 mock；import 路径更新）。
- 新增测试（全 mock，不触真实网络/LLM）：
  | 文件 | 覆盖 |
  | :--- | :--- |
  | `tests/test_schemas.py` | Classification 值域回退；Email alias `from` 往返 |
  | `tests/test_config_manager.py` | yaml 默认加载；env 覆盖 yaml；get_prompt 缓存命中 |
  | `tests/test_llm.py` | invoke_with_fallback：主调用抛错 → 返回 fallback；成功不触发 fallback |
  | `tests/test_tracing.py` | record_node/record_tool/record_tokens/get_last_run |
  | `tests/test_router.py` | resolve 命中/未命中；orchestrator 命名空间 route_map |
  | `tests/test_orchestrator.py` 增补 | 契约校验：缺 SKILL_META.name / ROUTES 无 build_subgraph → status=error |
- 现有测试文件改 import 路径后断言不变。

## 6. 迁移顺序（每步后测试全绿，可独立提交）

1. 建 `src/` 骨架：移动包（agent_core→src/core，skills→src/capabilities），更新全项目 import；`__init__.py` 补齐；跑测试。
2. `schemas.py` + 工具边界接入（fetcher/classifier 返回类型化模型；UI/节点改属性访问）。
3. `config_manager.py` + settings.yaml + prompts 外置（classification prompt 写入 config/prompts/email/）；config.py 删除。
4. `llm.py` + classifier 改造（LLM 调用走 core.llm + fallback）。
5. route 命名空间化 + state 补 capability 字段 + router.py。
6. orchestrator 契约校验。
7. checkpointer.py 抽象。
8. tracing.py + visualizer.py + `pages/01_可视化.py` + main.py 指标替换。
9. 全量回归（16 + 新增）+ 真实模式验证（45 封拉取 + 分类，行为与重构前一致）。

## 7. 风险与取舍

- **包结构移动是大 diff**：机械 churn，无行为变化；git 识别 rename，逐任务提交时 review 聚焦每步行为差异。
- **schemas 接入改动面**：改一批 dict 访问点（fetcher/classifier/ui/节点/测试），机械但量大；风险低。
- **可视化零依赖**：SVG 为静态图，无交互缩放/hover；如后续需要交互可加 plotly（纯 pip）。
- **messages 通道仍空**：会话消息指标 Phase 2 启用；本设计以 tracing 指标替代总览页死指标。
- **route 旧名不兼容**：`refresh_email` → `email.refresh`，一次性改名，测试与 UI 同步更新。

## 8. 后续（Phase 2 预留，不在本设计范围）

- 摘要/草拟/发送能力节点 + `interrupt()` 人工确认（write_internal/write_external 已就绪）。
- LLM 意图路由（router.resolve 演进）。
- Postgres checkpointer、OTel tracing 升级。
- 多能力并发时引入 `capabilities/<name>` 状态命名空间。
