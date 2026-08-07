# GM-Assistant — 智能邮件处理系统

面向总经理的个人助理级邮件处理平台。基于 **可扩展技能插件架构**：核心框架负责技能发现、工具注册与安全管控，业务能力以「技能」模块形式插拔扩展。

- **当前阶段**：Phase 1 最小闭环（邮件拉取 → 自动分类 → 前端展示）
- **运行模式**：无任何凭据即可 Mock 演示；填写 `.env` 后切换真实 IMAP + LLM

---

## 1. 项目结构

```
GM-Assistant/
├── agent_core/                  # 核心框架（与具体技能解耦）
│   ├── orchestrator.py          # 技能编排器：扫描 skills/，动态加载 skill_manifest.py
│   ├── state.py                   # AgentState：LangGraph 状态 schema
│   ├── tool_registry.py         # 工具注册中心（read / write_internal / write_external）
│   ├── safety.py                # 安全网关：check_permission() 权限判定
│   ├── logger.py                # 统一日志 + 敏感信息脱敏 + 近期日志缓冲
│   ├── graph.py                  # Agent 超级图：Router 入口 + 技能子图（MemorySaver）
├── skills/email/                # 业务技能：智能邮件处理
│   ├── skill_manifest.py        # 技能自描述：SKILL_META + get_tools() + get_status()
│   ├── mail_fetcher.py          # IMAP 拉取；未配置时使用 Mock 样例邮件
│   ├── email_classifier.py      # litellm 分类 + 关键词规则兜底
│   ├── ui_page.py               # Streamlit 页面渲染逻辑
│   └── prompts/                 # LLM 提示词
├── pages/01_邮件处理.py          # Streamlit 页面：极简转发到技能模块
├── main.py                      # 总览页：技能状态 / 工具计数 / 安全模式 / 最近日志
├── config.py                    # 全局配置（读取 .env）
├── .env.example                 # 环境变量示例（复制为 .env 使用）
├── requirements.txt
└── 需求文档.md
```

## 2. 平台骨架

核心框架分四层，职责单一、与具体技能完全解耦：

| 模块 | 职责 |
| :--- | :--- |
| `orchestrator` | 启动时扫描 `skills/*/skill_manifest.py`，动态导入并注册技能与工具。**单个技能加载失败不阻塞其他技能**（标记 status=error） |
| `tool_registry` | 工具注册中心，按名称集中管理 `ToolDefinition`（含读写类型） |
| `safety` | 安全网关，对每次工具调用做权限判定 |
| `logger` | 统一日志（自动脱敏） |
| `graph` | Agent 超级图：Router 入口 + 技能子图，checkpointer 持久化 |

编排层基于 **LangGraph**：Agent 超级图（Router 入口 + 技能子图），工具调用统一经安全网关 `safe_call` 包裹；技能=子图，由 orchestrator 扫描 `skill_manifest` 装配。

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

## 3. 插件机制（如何新增技能）

新技能只需两步，无需改动核心框架：

1. 在 `skills/` 下新建目录 `skills/<技能名>/`
2. 编写 `skill_manifest.py`，声明：

```python
from agent_core.tool_registry import TOOL_READ, ToolDefinition

# 1) 技能元信息
SKILL_META = {
    "name": "skill_name",
    "title": "技能显示名",
    "description": "一句话说明",
    "version": "0.1.0",
}

# 2) 声明工具及其权限类型
def get_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="some_tool",
            tool_type=TOOL_READ,            # read / write_internal / write_external
            module="skill_name",
            description="工具说明",
            handler=my_handler,             # 实际执行函数
        ),
    ]

# 3) 返回状态：active / not_configured / error
def get_status() -> str:
    return "active"

# 4) 可选：配置状态提示（展示在总览页）
def get_config_hint() -> str:
    return "IMAP 未配置 → 使用 Mock 样例邮件"
```

技能页面的 Streamlit UI 放在技能目录内的 `ui_page.py`，在 `pages/` 下建一个极简转发页即可被多页面自动发现。

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

访问 <http://localhost:8501>。总览页展示技能模块、工具计数、安全模式与最近日志；「邮件处理」页点击「刷新邮件」即可看到拉取 + 分类结果。

> Windows 提示：`conda run` 输出含 emoji 时会触发 GBK 编码崩溃（conda 自身 bug），请直接调用环境内的 `python.exe`。

## 5. 配置说明

复制 `.env.example` 为 `.env` 后按需填写。所有敏感信息仅从 `.env` 读取，代码中绝不硬编码。

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
| `IMAP_SERVER` / `IMAP_PORT` / `IMAP_EMAIL` / `IMAP_PASSWORD` | 空 | IMAP 邮箱配置 |
| `EMAIL_FETCH_LIMIT` | `20` | 每次拉取未读上限 |
| `EMAIL_BODY_PREVIEW_LEN` | `300` | 正文预览长度（控制 LLM token 消耗） |
| `LLM_MODE` | `mock` | `mock`=规则分类 / `real`=真实模型 |
| `LLM_MODEL` | `deepseek/deepseek-chat` | litellm 模型名，`provider/model` |
| `LLM_API_KEY` / `LLM_BASE_URL` | 空 | LLM 凭据与网关 |
| `ENABLE_WRITE_EXTERNAL` | `false` | 是否启用外部写工具 |

## 6. 开发路线

| 阶段 | 内容 | 状态 |
| :--- | :--- | :--- |
| **Phase 1** | 最小闭环：IMAP 拉取 + 分类（规则 + LLM）+ Web 展示 | ✅ 完成 |
| **Phase 2** | 摘要引擎 + 回复草拟（基础版）+ 草稿确认→发送链路 | 规划中 |
| **Phase 3** | 风格学习与优化（范文检索 + 反馈闭环） | 规划中 |
| **Phase 4** | 多邮箱与团队协作（转交建议、助理协作） | 规划中 |

Phase 2 起将使用到安全网关已预留的 `write_internal`（草稿）与 `write_external`（发送）权限位。

详细需求与安全网关规格见 [需求文档.md](需求文档.md)。
