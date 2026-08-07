# GM-Assistant — 智能邮件处理系统

面向总经理的个人助理级邮件处理平台。基于 **可扩展能力插件架构**：核心平台负责能力发现、工具注册与安全管控，业务能力以 `src/capabilities/` 下的「能力模块」形式插拔扩展。

- **当前阶段**：Phase 1 最小闭环（邮件拉取 → 自动分类 → 前端展示 + 图执行可视化）
- **运行模式**：无任何凭据即可 Mock 演示；填写 `.env` 后切换真实 IMAP + LLM

---

## 1. 项目结构

```
GM-Assistant/
├── src/
│   ├── core/                        # 平台运行时（与具体能力解耦）
│   │   ├── schemas.py               # Pydantic 模型：Email / Classification / EmailClassified
│   │   ├── config_manager.py        # 全局配置：settings.yaml + .env，config 单例 + get_prompt()
│   │   ├── llm.py                   # LLM 统一调用层：completion() + invoke_with_fallback()
│   │   ├── state.py                 # AgentState：LangGraph 状态 schema（含 capability 字段）
│   │   ├── router.py                # 路由解析：命名空间 route → 能力节点（resolve()）
│   │   ├── graph.py                 # Agent 超级图：route 入口 + 各能力子图，agent 单例 + checkpointer
│   │   ├── orchestrator.py          # 能力编排器：扫描 capabilities/*/manifest.py + 契约校验
│   │   ├── safety.py                # 安全网关：gateway + safe_call（工具调用审计）
│   │   ├── tool_registry.py         # 工具注册中心（read / write_internal / write_external）
│   │   ├── checkpointer.py          # 会话持久化抽象（build_checkpointer，当前 MemorySaver）
│   │   ├── tracing.py               # 执行观测：tracer + @traced（轨迹 / 工具审计 / token）
│   │   ├── visualizer.py            # 图结构渲染：render_graph_svg()
│   │   └── logger.py                # 统一日志 + 敏感信息脱敏 + 近期日志缓冲
│   └── capabilities/
│       └── email/                   # 能力模块：智能邮件处理
│           ├── manifest.py          # 能力自描述：SKILL_META + ROUTES + 再导出 get_tools + build_subgraph
│           ├── graph.py             # 能力子图：fetch_node → classify_node（@traced）
│           ├── fetcher.py           # IMAP 拉取；未配置时使用 Mock 样例邮件
│           ├── classifier.py        # litellm 分类 + 关键词规则兜底
│           ├── tools.py             # 能力声明的工具列表（ToolDefinition）
│           └── ui_page.py           # Streamlit 页面渲染逻辑
├── config/
│   ├── settings.yaml                # 非敏感运行参数（llm / email / safety / tracing）
│   └── prompts/
│       └── email/                   # LLM 提示词模板（classification / summary / draft）
├── pages/
│   ├── 01_可视化.py                  # 图执行可视化：DAG + 最近执行轨迹 + token/工具审计 + 日志
│   └── 02_邮件处理.py                # 邮件处理页：极简转发到 src.capabilities.email.ui_page
├── main.py                          # 总览页：技能模块 / 工具计数 / 安全模式 / 最近执行 / 日志
├── .env.example                     # 环境变量示例（复制为 .env 使用；密钥仅从此读取）
├── requirements.txt
└── 需求文档.md
```

## 2. 平台骨架

核心平台分四层，职责单一、与具体能力完全解耦：

| 模块 | 职责 |
| :--- | :--- |
| `schemas` | Pydantic 类型化边界：`Email` / `Classification` / `EmailClassified`，值域归一化在 validator 内兜底 |
| `config_manager` | 读取 `config/settings.yaml` + `.env`，`config` 单例，`get_prompt()` 缓存读取 `config/prompts/` |
| `llm` | 统一 LLM 调用：`completion()` 封装 litellm，`invoke_with_fallback()` 提供「主调用失败 → 兜底」容灾 |
| `orchestrator` | 启动时扫描 `src/capabilities/*/manifest.py`，动态加载并注册能力与工具。**单个能力加载失败不阻塞其他能力**（标记 status=error） |
| `tool_registry` | 工具注册中心，按名称集中管理 `ToolDefinition`（含读写类型） |
| `safety` | 安全网关，对每次工具调用做权限判定；`safe_call` 统一包裹执行并记录工具审计 |
| `graph` | Agent 超级图：route 入口 + 能力子图，checkpointer 持久化 |
| `checkpointer` | 会话持久化抽象（当前 MemorySaver，可替换为 Postgres，接口不变） |
| `tracing` | 执行观测：节点轨迹、工具调用审计、token 用量（`tracer` + `@traced` 装饰器） |
| `visualizer` | 图结构渲染（`render_graph_svg`，已执行节点高亮） |
| `logger` | 统一日志（自动脱敏，正文不落盘） |

编排层基于 **LangGraph**：Agent 超级图（Router 入口 + 能力子图），工具调用统一经安全网关 `safe_call` 包裹；能力=子图，由 orchestrator 扫描 `manifest.py` 装配，route 以「能力名.action」命名空间分发（如 `email.refresh`）。

### 权限模型（安全网关）

工具声明为三类，权限逐级收紧：

| 工具类型 | 含义 | 权限 |
| :--- | :--- | :--- |
| `read` | 读操作（拉取、分类） | **默认放行** |
| `write_internal` | 内部写（如存草稿） | **需用户确认** |
| `write_external` | 外部写（如发送邮件） | **默认禁用**，需 `ENABLE_WRITE_EXTERNAL=true` 显式开启 |

### 日志安全约定

- 统一格式：`[时间] [模块] [级别] 消息`，输出到控制台 + `logs/agent.log`
- 自动脱敏：邮箱地址、密码/密钥类字段（`redact()` 独立可测）
- **邮件正文一律不写入日志**，只记录 ID 与元数据

## 3. 插件机制（如何新增能力）

新能力只需三步，无需改动核心平台：

1. 在 `src/capabilities/` 下新建目录 `src/capabilities/<能力名>/`（含 manifest + tools + graph + ui_page）
2. 编写 `tools.py` 声明工具，`manifest.py` 声明能力自描述（SKILL_META + ROUTES + 再导出 get_tools + build_subgraph），`graph.py` 构建能力子图
3. 在 `pages/` 下建一个极简转发页调用能力内的 `ui_page.py`

示例（结构同 `src/capabilities/email/`）：

```python
# src/capabilities/<name>/tools.py — 声明工具及其权限类型
from src.core.tool_registry import TOOL_READ, ToolDefinition

def get_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="some_tool",
            tool_type=TOOL_READ,            # read / write_internal / write_external
            module="<name>",
            description="工具说明",
            handler=my_handler,             # 实际执行函数
        ),
    ]
```

```python
# src/capabilities/<name>/manifest.py — 能力自描述（由 orchestrator 扫描发现）
from src.capabilities.<name>.tools import get_tools  # 从 tools.py 再导出

# 本能力子图可处理的裸 route；orchestrator 自动加能力名前缀 → "<name>.<action>"
ROUTES = ["some_action"]

def build_subgraph():
    from src.capabilities.<name>.graph import build_<name>_subgraph
    return build_<name>_subgraph()

# 1) 能力元信息
SKILL_META = {
    "name": "<name>",
    "title": "技能显示名",
    "description": "一句话说明",
    "version": "0.1.0",
}

# 2) 返回状态：active / not_configured / error
def get_status() -> str:
    return "active"

# 3) 可选：配置状态提示（展示在总览页）
def get_config_hint() -> str:
    return "IMAP 未配置 → 使用 Mock 样例邮件"
```

orchestrator 对每个 manifest 做**契约校验**（`SKILL_META.name`、`get_tools()` 返回 `ToolDefinition`、`ROUTES` 非空时必须提供 `build_subgraph()`）；校验失败仅将该能力标记 `status=error`，**不阻塞其他能力加载**。声明的裸 `ROUTES` 会被加上能力名前缀（如 `email.refresh`），供超级图按命名空间 route 分发。

能力页面的 Streamlit UI 放在能力目录内的 `ui_page.py`，在 `pages/` 下建一个极简转发页即可被多页面自动发现。

## 4. 启动方式

### 环境准备（首次）

```bash
# 安装依赖（conda 环境 GM-Assistant，Python 3.12）
D:\conda_envs\GM-Assistant\python.exe -m pip install -r requirements.txt
```

### 启动应用

```bash
cd C:\intern\GM-Assistant
D:\conda_envs\GM-Assistant\python.exe -m streamlit run main.py
```

访问 <http://localhost:8501>。总览页展示能力模块、工具计数、安全模式、最近执行与最近日志；「邮件处理」页点击「刷新邮件」即可看到拉取 + 分类结果；「可视化」页展示图结构 DAG（已执行节点高亮）、最近一次执行轨迹、token 用量与工具调用审计。

> Windows 提示：`conda run` 输出含 emoji 时会触发 GBK 编码崩溃（conda 自身 bug），请直接调用环境内的 `python.exe`。

## 5. 配置说明

配置分两层：**非敏感运行参数**放 `config/settings.yaml`（llm / email / safety / tracing），**敏感信息**（IMAP 密码、API Key）只在 `.env`。取值优先级：环境变量 > `settings.yaml` > 代码默认值。复制 `.env.example` 为 `.env` 后按需填写。

### Mock 模式（零配置，开箱即用）

- **IMAP 未配置** → 使用内置 8 封样例邮件（覆盖四档紧急度）
- **LLM 未配置**（`LLM_MODE=mock`）→ 使用关键词规则分类

### 接入真实数据

```ini
# 邮箱（QQ 邮箱密码处填「授权码」，非登录密码）
IMAP_SERVER=imap.qq.com
IMAP_PORT=993
IMAP_EMAIL=you@qq.com
IMAP_PASSWORD=授权码
IMAP_USE_SSL=true

# LLM
LLM_MODE=real
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=sk-xxx
# 兼容 OpenAI 协议的网关地址（OneAPI/Ollama/私有网关），留空走官方接口
LLM_BASE_URL=

# 安全网关：外部写（如发送邮件）默认禁用
ENABLE_WRITE_EXTERNAL=false
```

### 关键环境变量

| 变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `IMAP_SERVER` / `IMAP_PORT` / `IMAP_EMAIL` / `IMAP_PASSWORD` | 空 | IMAP 邮箱配置（密钥仅从此读取） |
| `EMAIL_FETCH_LIMIT` | `20` | 每次拉取未读上限（`settings.yaml` 亦可配） |
| `EMAIL_BODY_PREVIEW_LEN` | `300` | 正文预览长度（控制 LLM token 消耗） |
| `LLM_MODE` | `mock` | `mock`=规则分类 / `real`=真实模型 |
| `LLM_MODEL` | `deepseek/deepseek-chat` | litellm 模型名，`provider/model` |
| `LLM_API_KEY` / `LLM_BASE_URL` | 空 | LLM 凭据与网关 |
| `ENABLE_WRITE_EXTERNAL` | `false` | 是否启用外部写工具 |

> `config/settings.yaml` 提供同名默认值（`llm.mode` / `llm.model` / `email.fetch_limit` / `email.body_preview_len` / `safety.enable_write_external` / `tracing.*`），可被上述环境变量覆盖。

## 6. 开发路线

| 阶段 | 内容 | 状态 |
| :--- | :--- | :--- |
| **Phase 1** | 最小闭环：IMAP 拉取 + 分类（规则 + LLM）+ Web 展示 + 图执行可视化 | ✅ 完成 |
| **Phase 2** | 摘要引擎 + 回复草拟（基础版）+ 草稿确认→发送链路 | 规划中 |
| **Phase 3** | 风格学习与优化（范文检索 + 反馈闭环） | 规划中 |
| **Phase 4** | 多邮箱与团队协作（转交建议、助理协作） | 规划中 |

Phase 2 起将使用到安全网关已预留的 `write_internal`（草稿）与 `write_external`（发送）权限位。

详细需求与安全网关规格见 [需求文档.md](需求文档.md)。
