# 后端结构化重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GM-Assistant 改造为能力平台形态：`src/core/` 平台运行时 + `src/capabilities/` 能力插件（email 是第一个），实现类型化模型、配置外置、LLM 统一、route 命名空间、契约校验、可观测可视化。

**Architecture:** 参考 `gaokao_tutor` 项目（仅借鉴模式，独立仓库）。包移动 `agent_core/`→`src/core/`、`skills/`→`src/capabilities/`；Pydantic schemas 做工具边界契约；`config/settings.yaml` + `.env` 覆盖管理非敏感配置，prompt 外置 `config/prompts/`；`src/core/llm.py` 统一 LLM 调用 + fallback 容灾；route 以 `技能名.route` 命名空间防撞名；orchestrator 扫描时校验 manifest 契约；`tracing.py` 记录执行轨迹/工具审计/token，`visualizer.py` 零依赖 SVG 渲染图结构；Streamlit 新增可视化页。

**Tech Stack:** LangGraph（已用）、Pydantic v2（已装，2.13.4）、litellm（已用）、pyyaml（已装）、Streamlit（已用）。

设计文档：`docs/superpowers/specs/2026-08-07-backend-restructure-design.md`（本计划的唯一需求来源）。

## Global Constraints

- 项目根 = `C:/intern/GM-Assistant`（独立 git 仓库，分支 `main`）。
- Python 解释器直接用 `D:/conda_envs/GM-Assistant/python.exe`（Windows，**勿用 `conda run`**）。
- 测试命令：在项目根运行 `D:/conda_envs/GM-Assistant/python.exe -m pytest`（`pytest.ini` 已设 `pythonpath = .`）。
- **强制 Mock**：conftest 的 `mock_env` fixture 清空 IMAP 凭据 + `LLM_MODE=mock`。任何任务禁止触发真实 IMAP/LLM 调用。
- 每任务完成后，现有 16 tests 与已新增测试必须全绿。
- 所有新 import 一律 `src.*` 前缀（如 `from src.core.graph import agent`）。
- 目标目录结构与文件命名严格按设计文档「3. 目标目录结构」「4. 各设计点规格」。
- git 提交：用户偏好「git 提交由用户自行处理」。执行开始时（subagent-driven-development）由控制器与用户确认是否按任务提交。

---

### Task 1: src/ 包骨架 + 包结构移动

**Files:**
- Create: `src/__init__.py`、`src/core/__init__.py`、`src/capabilities/__init__.py`、`src/capabilities/email/__init__.py`、`src/tools/__init__.py`
- Move（`git mv`）：`agent_core/*` → `src/core/*`；`skills/email/*` → `src/capabilities/email/*`；`config.py` → `src/core/config_manager.py`
- Modify: 全项目 import 更新 + 路径计算修正（见下）
- Test: 现有 6 个测试文件 import 更新（断言不变）

**Interfaces:**
- Consumes: 现有代码（本任务不改行为，仅移动 + 改引用）
- Produces:
  - `src.core.*`（graph/logger/orchestrator/safety/state/tool_registry/config_manager）
  - `src.capabilities.email.*`（graph/manifest/fetcher/classifier/ui_page/prompts）
  - 模块重命名：`skills/email/skill_manifest.py`→`manifest.py`、`mail_fetcher.py`→`fetcher.py`、`email_classifier.py`→`classifier.py`
  - 单例对象名不变：`config`（来自 `src.core.config_manager`）、`orchestrator`、`agent`、`logger`、`gateway`、`registry`

**步骤：**

- [ ] **Step 1: 创建 `__init__.py` 骨架**

```bash
mkdir -p src/core src/capabilities/email src/tools
: > src/__init__.py
: > src/core/__init__.py
: > src/capabilities/__init__.py
: > src/capabilities/email/__init__.py
: > src/tools/__init__.py
```

- [ ] **Step 2: git mv 移动文件**

```bash
git mv agent_core/graph.py src/core/graph.py
git mv agent_core/logger.py src/core/logger.py
git mv agent_core/orchestrator.py src/core/orchestrator.py
git mv agent_core/safety.py src/core/safety.py
git mv agent_core/state.py src/core/state.py
git mv agent_core/tool_registry.py src/core/tool_registry.py
git mv agent_core/__init__.py src/core/__init__.py
git mv skills/email/skill_manifest.py src/capabilities/email/manifest.py
git mv skills/email/mail_fetcher.py src/capabilities/email/fetcher.py
git mv skills/email/email_classifier.py src/capabilities/email/classifier.py
git mv skills/email/graph.py src/capabilities/email/graph.py
git mv skills/email/ui_page.py src/capabilities/email/ui_page.py
git mv skills/email/__init__.py src/capabilities/email/__init__.py
git mv skills/email/prompts src/capabilities/email/prompts
git mv config.py src/core/config_manager.py
# 若残留空目录
rmdir agent_core skills/email skills 2>/dev/null || true
```

- [ ] **Step 2.5: 抽取 `src/capabilities/email/tools.py`（spec 目录树要求）**

把 manifest 里的工具声明迁到独立文件 `tools.py`，manifest 重新导出 `get_tools`（orchestrator 校验的仍是 `manifest.get_tools`）。

创建 `src/capabilities/email/tools.py`：
```python
# -*- coding: utf-8 -*-
"""email 能力声明的工具（fetch_emails / classify_emails）。

工具句柄指向 fetcher/classifier 的模块级函数；权限类型在此集中声明。
"""
from src.capabilities.email.classifier import classify_emails
from src.capabilities.email.fetcher import fetch_emails
from src.core.tool_registry import TOOL_READ, ToolDefinition


def get_tools() -> list[ToolDefinition]:
    """声明本能力提供的工具及其权限类型。"""
    return [
        ToolDefinition(
            name="fetch_emails",
            tool_type=TOOL_READ,
            module="email",
            description="从 IMAP 邮箱拉取最近未读邮件（未配置时使用 Mock 样例）",
            handler=fetch_emails,
            requires_config=["IMAP_SERVER", "IMAP_EMAIL", "IMAP_PASSWORD"],
        ),
        ToolDefinition(
            name="classify_emails",
            tool_type=TOOL_READ,
            module="email",
            description="对邮件列表进行 LLM/规则分类",
            handler=classify_emails,
        ),
    ]
```

`src/capabilities/email/manifest.py` 顶部删掉内联的 `get_tools()` 定义（连同 `TOOL_READ`/`ToolDefinition` 的 import），改为一行导出：
```python
from src.capabilities.email.tools import get_tools
```
（`SKILL_META`、`build_subgraph`、`get_status`、`get_config_hint`、`ROUTES` 仍留在 manifest。）

- [ ] **Step 3: 更新全项目 import（映射表）**

| 旧 | 新 |
| :--- | :--- |
| `from agent_core.logger import logger` | `from src.core.logger import logger` |
| `from agent_core.orchestrator import orchestrator` | `from src.core.orchestrator import orchestrator` |
| `from agent_core.state import AgentState` | `from src.core.state import AgentState` |
| `from agent_core.safety import ...` | `from src.core.safety import ...` |
| `from agent_core.tool_registry import ...` | `from src.core.tool_registry import ...` |
| `from agent_core.graph import agent` / `route_path` | `from src.core.graph import ...` |
| `from config import config` | `from src.core.config_manager import config` |
| `from skills.email.ui_page import render` | `from src.capabilities.email.ui_page import render` |
| `from skills.email.email_classifier import ...` | `from src.capabilities.email.classifier import ...` |
| `from skills.email.mail_fetcher import ...` | `from src.capabilities.email.fetcher import ...` |
| `from skills.email.prompts.classification import ...` | `from src.capabilities.email.prompts.classification import ...` |

涉及文件（逐个改）：
- `src/core/graph.py`：`agent_core.*` → `src.core.*`
- `src/core/safety.py`：`from config import config` → `from src.core.config_manager import config`；`agent_core.tool_registry` → `src.core.tool_registry`
- `src/core/orchestrator.py`：`agent_core.*` → `src.core.*`
- `src/capabilities/email/manifest.py`：`agent_core.tool_registry` → `src.core.tool_registry`；`from config import config` → `from src.core.config_manager import config`；`skills.email.email_classifier` → `src.capabilities.email.classifier`；`skills.email.mail_fetcher` → `src.capabilities.email.fetcher`
- `src/capabilities/email/graph.py`：`agent_core.*` → `src.core.*`
- `src/capabilities/email/classifier.py`：`agent_core.logger` → `src.core.logger`；`from config import config` → `from src.core.config_manager import config`；`skills.email.prompts.classification` → `src.capabilities.email.prompts.classification`
- `src/capabilities/email/fetcher.py`：`agent_core.logger` → `src.core.logger`；`from config import config` → `from src.core.config_manager import config`
- `src/capabilities/email/ui_page.py`：`agent_core.logger` → `src.core.logger`；`from config import config` → `from src.core.config_manager import config`
- `main.py`：全部 `agent_core.*` → `src.core.*`；`from config import config` → `from src.core.config_manager import config`
- `pages/01_邮件处理.py`：`from skills.email.ui_page import render` → `from src.capabilities.email.ui_page import render`
- `tests/conftest.py`：`from config import config` → `from src.core.config_manager import config`
- `tests/test_*.py`：`agent_core.*` → `src.core.*`、`skills.email.*` → `src.capabilities.email.*`（断言不变）

- [ ] **Step 4: 修正三个基于 `__file__` 的路径计算（关键，防回归）**

原代码假设模块在「根的一级子目录」，移动后层级变了，必须改为从 `src/core/` 上溯到项目根：

`src/core/config_manager.py`（原 config.py）：
```python
# 项目根目录（config_manager.py: src/core/ → 根）
BASE_DIR = Path(__file__).resolve().parents[2]
```

`src/core/orchestrator.py`：
```python
# 能力目录：项目根/src/capabilities
_SKILLS_DIR = Path(__file__).resolve().parents[1] / "capabilities"
# 扫描 glob 改（manifest 已重命名）
manifests = sorted(skills_dir.glob("*/manifest.py"))
```

`src/core/logger.py`：
```python
# 日志目录：项目根/logs
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
```

- [ ] **Step 5: 全量测试验证**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 16 passed。

- [ ] **Step 6: Commit**

```bash
git add -A  # 或按实际变更文件
git commit -m "refactor: task 1 - src/ package layout, agent_core->src/core, skills->src/capabilities"
```
（按 Global Constraints，实际提交由用户确认执行方式。）

---

### Task 2: schemas.py + 工具边界类型化

**Files:**
- Create: `src/core/schemas.py`、`tests/test_schemas.py`
- Modify: `src/capabilities/email/fetcher.py`、`src/capabilities/email/classifier.py`、`src/capabilities/email/ui_page.py`
- Test: `tests/test_schemas.py`（新增）

**Interfaces:**
- Consumes: Task 1 的 `src.core.*`、`src.capabilities.email.*`
- Produces:
  - `src.core.schemas.Email` / `Classification` / `EmailClassified`（Pydantic）
  - `fetch_emails(...) -> list[Email]`
  - `classify_emails(emails: list[Email]) -> list[EmailClassified]`
  - `EmailClassified` 可经 `model_dump(by_alias=True)` 得到含 `from` 键的 dict

- [ ] **Step 1: 写失败测试 `tests/test_schemas.py`**

```python
# -*- coding: utf-8 -*-
from src.core.schemas import Classification, Email, EmailClassified


def test_classification_normalizes_bad_urgency():
    c = Classification(urgency="不存在的级别", action="需要回复")
    assert c.urgency == "普通"


def test_classification_normalizes_bad_action():
    c = Classification(urgency="紧急", action="不存在的动作")
    assert c.action == "仅需阅读"


def test_email_accepts_from_alias():
    e = Email(id="1", from="x@y.com", subject="你好")
    assert e.from_ == "x@y.com"
    assert e.model_dump(by_alias=True)["from"] == "x@y.com"


def test_email_classified_roundtrip():
    ec = EmailClassified(id="1", from="a@b.com", classification=Classification(urgency="紧急", action="需要回复"))
    d = ec.model_dump(by_alias=True)
    assert d["from"] == "a@b.com"
    assert d["classification"]["urgency"] == "紧急"
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_schemas.py
```
Expected: FAIL（`ModuleNotFoundError: No module named 'src.core.schemas'`）。

- [ ] **Step 3: 创建 `src/core/schemas.py`**

```python
# -*- coding: utf-8 -*-
"""Pydantic 类型化模型（工具边界契约）。

fetch_emails → list[Email]；classify_emails → list[EmailClassified]。
值域归一化在 field_validator 内做回退，等价于原 classifier._validate_result。
"""
from pydantic import BaseModel, Field, field_validator

URGENCY_LEVELS = ("紧急", "重要", "普通", "可忽略")
ACTIONS = ("需要回复", "仅需阅读", "可转交", "可归档")


class Classification(BaseModel):
    urgency: str
    action: str
    category_tag: str = "其他"
    reason: str = ""
    confidence: float | None = None  # Phase 2 LLM 置信度

    @field_validator("urgency")
    @classmethod
    def _norm_urgency(cls, v: str) -> str:
        return v if v in URGENCY_LEVELS else "普通"

    @field_validator("action")
    @classmethod
    def _norm_action(cls, v: str) -> str:
        return v if v in ACTIONS else "仅需阅读"


class Email(BaseModel):
    id: str
    subject: str = ""
    from_: str = Field(default="", alias="from")  # 对外序列化/构造仍用 "from"
    received_at: str = ""
    body_preview: str = ""

    model_config = {"populate_by_name": True}


class EmailClassified(Email):
    classification: Classification
```

- [ ] **Step 4: 改造 `fetcher.py` 返回 `list[Email]`**

- 顶部 `from src.core.schemas import Email`。
- `fetch_recent(...) -> list[Email]`；`_fetch_mock` 返回 `[Email(**m) for m in _MOCK_EMAILS][:limit]`（mock dict 含 `"from"` 键，`populate_by_name` 接受）；`_fetch_imap` 收集 `emails: list[Email] = []`，`emails.append(self._to_struct(num, message))`。
- `_to_struct(...) -> Email`（返回类型与字段键不变，Pydantic alias 处理 `from`）：
```python
return Email(
    id=str(msg_id),
    subject=cls._decode_mime(message.get("Subject", "")),
    from=cls._decode_mime(message.get("From", "")),
    received_at=cls._decode_date(message.get("Date", "")),
    body_preview=cls._extract_preview(message, config.EMAIL_BODY_PREVIEW_LEN),
)
```
- 模块级工具句柄同步类型化（manifest/tools.py 引用的正是它）：
```python
def fetch_emails(limit: int | None = None, unread_only: bool = True) -> list[Email]:
    """技能对外工具：拉取最近未读邮件。"""
    return MailFetcher().fetch_recent(limit=limit, unread_only=unread_only)
```
- 注释与 `__all__` 相应更新（`__all__ = ["MailFetcher", "fetch_emails"]`）。

- [ ] **Step 5: 改造 `classifier.py` 返回 `Classification` / `list[EmailClassified]`**

- 顶部：`from src.core.schemas import Classification, EmailClassified`。
- `classify_one(email: Email) -> Classification`：
```python
def classify_one(self, email: Email) -> Classification:
    text = f"主题：{email.subject}\n正文：{email.body_preview}"[:_CLASSIFY_TEXT_LEN]
    if self._config.llm_configured:
        try:
            return _llm_classify(text)
        except Exception as e:
            logger.warning("email.classifier", f"LLM 分类失败，退回规则分类: {e}")
    return _mock_classify(text)
```
- `_mock_classify(text) -> Classification`（构造对象，validator 自动归一化）：
```python
def _mock_classify(text: str) -> Classification:
    lower = text.lower()
    if _first_hit(_URGENT_KEYWORDS, lower):
        urgency = "紧急"
    elif _first_hit(_IGNORABLE_KEYWORDS, lower):
        urgency = "可忽略"
    elif _first_hit(_IMPORTANT_KEYWORDS, lower):
        urgency = "重要"
    else:
        urgency = "普通"
    hit_reply = _first_hit(_REPLY_KEYWORDS, lower)
    hit_forward = _first_hit(_FORWARD_KEYWORDS, lower)
    if hit_reply:
        action = "需要回复"; reason = f"含请求性用语「{hit_reply}」"
    elif hit_forward:
        action = "可转交"; reason = f"含汇报/知悉类用语「{hit_forward}」"
    elif urgency == "可忽略":
        action = "可归档"; reason = "系统通知/订阅类，无需处理"
    else:
        action = "仅需阅读"; reason = "信息同步类，无需回复"
    if any(k in lower for k in ("客户", "合同", "合作", "订单", "供应商", "报价")):
        tag = "客户-业务"
    elif urgency == "紧急":
        tag = "紧急事件"
    elif any(k in lower for k in ("审批", "预算", "汇报", "会议", "产品")):
        tag = "内部-管理"
    elif urgency == "可忽略":
        tag = "系统-通知"
    else:
        tag = "其他"
    return Classification(urgency=urgency, action=action, category_tag=tag, reason=reason)
```
- `_llm_classify(text) -> Classification`：解析 JSON 后构造：
```python
def _llm_classify(text: str) -> Classification:
    content = _llm_completion_text(text)  # Task 5 换成 src.core.llm.completion
    raw = _parse_json(content)
    return Classification(
        urgency=raw.get("urgency", "普通"),
        action=raw.get("action", "仅需阅读"),
        category_tag=str(raw.get("category_tag", "") or "其他"),
        reason=str(raw.get("reason", "") or ""),
    )
```
  其中 `_llm_completion_text` 即原 `_llm_classify` 的 litellm 调用体（本任务先保留原位；Task 5 移除）。
- `classify_many(emails: list[Email]) -> list[EmailClassified]`：
```python
def classify_many(self, emails: list[Email]) -> list[EmailClassified]:
    results = [
        EmailClassified(**email.model_dump(by_alias=True), classification=self.classify_one(email))
        for email in emails
    ]
    logger.info("email.classifier", f"批量分类完成，共 {len(results)} 封")
    return results
```
- 模块级工具句柄同步类型化（manifest/tools.py 引用的正是它），`_validate_result` 删除（归一化已由 validator 承担）：
```python
def classify_emails(emails: list[Email]) -> list[EmailClassified]:
    """技能对外工具：对邮件列表做批量分类。"""
    return EmailClassifier().classify_many(emails)


__all__ = ["EmailClassifier", "classify_emails", "URGENCY_LEVELS", "ACTIONS"]
```

- [ ] **Step 6: 改造 `ui_page.py` 用模型属性访问**

`_render_groups`：`urgency = (item.get("classification") or {}).get("urgency", "普通")` → `urgency = item.classification.urgency`。

`_render_email`：
```python
subject = item.subject or "（无主题）"
sender = item.from_ or "未知发件人"
received = item.received_at or ""
cls = item.classification
```
其下 `cls.get('urgency', '?')` → `cls.urgency`、`cls.action`、`cls.category_tag`、`cls.reason`；`item.get("body_preview", "（无正文）")` → `item.body_preview or "（无正文）"`。

（`_refresh()` 存 session_state 的仍是 `result.get("classified")`，即 `list[EmailClassified]`，无需改。）

- [ ] **Step 7: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 16 + 4 = 20 passed。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: task 2 - typed schemas (Email/Classification) at tool boundary"
```

---

### Task 3: config_manager 重写 + settings.yaml + prompts 外置

**Files:**
- Create: `config/settings.yaml`、`config/prompts/email/classification.txt`
- Modify: `src/core/config_manager.py`（内部重写为 yaml + env 覆盖 + get_prompt）、`src/capabilities/email/classifier.py`（prompt 经 `config.get_prompt` 取）
- Delete: `src/capabilities/email/prompts/`（其 `classification.py` 内容迁入 txt）
- Test: `tests/test_config_manager.py`（新增）

**Interfaces:**
- Consumes: Task 1 的 `src.core.config_manager` 模块位置；`config` 单例对象接口不变（`config.IMAP_SERVER`、`config.imap_configured`、`config.llm_configured` 等）。
- Produces:
  - `Config` 新增属性：`LLM_TEMPERATURE`、`TRACING_ENABLED`、`TRACING_RECENT_MAXLEN`（读自 yaml）
  - `Config.get_prompt(name: str) -> str`（线程安全缓存；`name` 用 `能力.名`，如 `email.classification`）
  - prompt 加载路径：`config/prompts/<能力>/<名>.txt`

- [ ] **Step 1: 写失败测试 `tests/test_config_manager.py`**

```python
# -*- coding: utf-8 -*-
from src.core.config_manager import Config


def test_yaml_defaults_loaded():
    c = Config()
    assert c.EMAIL_FETCH_LIMIT >= 1
    assert c.LLM_MODE in ("mock", "real")


def test_env_overrides_yaml(monkeypatch):
    monkeypatch.setenv("EMAIL_FETCH_LIMIT", "5")
    c = Config()
    assert c.EMAIL_FETCH_LIMIT == 5


def test_get_prompt_loads_and_caches():
    c = Config()
    p1 = c.get_prompt("email.classification")
    p2 = c.get_prompt("email.classification")
    assert p1 == p2
    assert len(p1) > 0
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_config_manager.py
```
Expected: FAIL（`Config` 尚无 `get_prompt`）。

- [ ] **Step 3: 创建 `config/settings.yaml`**

```yaml
# GM-Assistant 运行参数（非敏感）。密钥只在 .env，绝不入此文件。
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

- [ ] **Step 4: 创建 `config/prompts/email/classification.txt`**

把 `src/capabilities/email/prompts/classification.py` 的 `SYSTEM_PROMPT` 字符串**内容原样**写入本文件（UTF-8）。然后删除 `src/capabilities/email/prompts/` 目录（含 `__init__.py`、`classification.py`）。

再创建两个 Phase 2 预留占位文件（spec 目录树要求）：
- `config/prompts/email/summary.txt`：内容一行 `# Phase 2 预留：邮件摘要 prompt`
- `config/prompts/email/draft.txt`：内容一行 `# Phase 2 预留：回复草拟 prompt`

- [ ] **Step 5: 重写 `src/core/config_manager.py`**

```python
# -*- coding: utf-8 -*-
"""全局配置：settings.yaml + .env 覆盖 + prompt 模板缓存。

- 非敏感运行参数放 config/settings.yaml（默认值来源）。
- 密钥（IMAP 密码、API Key 等）只在 .env，绝不入 yaml。
- 取值优先级：环境变量 > settings.yaml > 代码默认值。
- config 为全局单例；get_prompt() 线程安全缓存读取 config/prompts/。
"""
import functools
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录（src/core/config_manager.py: parents[2] = 根）
BASE_DIR = Path(__file__).resolve().parents[2]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


class Config:
    """全部配置项；来源 yaml + 环境变量。"""

    def __init__(self) -> None:
        load_dotenv(BASE_DIR / ".env")
        self._yaml = self._load_yaml()

        # ---------- LLM ----------
        self.LLM_MODE = os.getenv("LLM_MODE") or self._yaml["llm"]["mode"]
        self.LLM_MODEL = os.getenv("LLM_MODEL") or self._yaml["llm"]["model"]
        self.LLM_BASE_URL = os.getenv("LLM_BASE_URL") or self._yaml["llm"]["base_url"]
        self.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        self.LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or self._yaml["llm"]["temperature"])

        # ---------- 邮箱 (IMAP)，密钥仅来自环境 ----------
        self.IMAP_SERVER = os.getenv("IMAP_SERVER", "")
        self.IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
        self.IMAP_EMAIL = os.getenv("IMAP_EMAIL", "")
        self.IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
        self.IMAP_USE_SSL = _as_bool(os.getenv("IMAP_USE_SSL"), True)
        self.EMAIL_FETCH_LIMIT = int(os.getenv("EMAIL_FETCH_LIMIT") or self._yaml["email"]["fetch_limit"])
        self.EMAIL_BODY_PREVIEW_LEN = int(os.getenv("EMAIL_BODY_PREVIEW_LEN") or self._yaml["email"]["body_preview_len"])

        # ---------- 安全网关 ----------
        self.ENABLE_WRITE_EXTERNAL = _as_bool(
            os.getenv("ENABLE_WRITE_EXTERNAL"), self._yaml["safety"]["enable_write_external"]
        )

        # ---------- 观测 ----------
        self.TRACING_ENABLED = bool(self._yaml["tracing"]["enabled"])
        self.TRACING_RECENT_MAXLEN = int(self._yaml["tracing"]["recent_maxlen"])

    @staticmethod
    def _load_yaml() -> dict:
        with open(BASE_DIR / "config" / "settings.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ---------- 便捷判断 ----------
    @property
    def imap_configured(self) -> bool:
        return bool(self.IMAP_SERVER and self.IMAP_EMAIL and self.IMAP_PASSWORD)

    @property
    def llm_configured(self) -> bool:
        return self.LLM_MODE == "real" and bool(self.LLM_API_KEY)

    # ---------- prompt 模板 ----------
    @functools.lru_cache(maxsize=64)
    def get_prompt(self, name: str) -> str:
        """按「能力.名」读取 config/prompts/<能力>/<名>.txt（UTF-8，带缓存）。"""
        rel = name.replace(".", "/")
        return (BASE_DIR / "config" / "prompts" / f"{rel}.txt").read_text(encoding="utf-8")


# 全局单例
config = Config()
```

注意：`mock_env`（conftest）monkeypatch 的是 `config` 单例的属性，本重构后仍是实例属性，无需改 conftest。

- [ ] **Step 6: 改 `classifier.py` 用 get_prompt**

`_llm_classify`（含 Task 2 的 `_llm_completion_text` 处）取系统提示改为：
```python
from src.core.config_manager import config
...
def _llm_classify(text: str) -> Classification:
    content = _llm_completion_text(text, config.get_prompt("email.classification"))
    ...
```
即把 `SYSTEM_PROMPT` 的引用替换为 `config.get_prompt("email.classification")`，并删除对 `src.capabilities.email.prompts.classification` 的 import。

- [ ] **Step 7: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 20 + 3 = 23 passed。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: task 3 - config manager (yaml+env+prompt cache), prompts externalized"
```

---

### Task 4: tracing.py（执行轨迹记录器）

**Files:**
- Create: `src/core/tracing.py`、`tests/test_tracing.py`
- Test: `tests/test_tracing.py`（新增）

**Interfaces:**
- Consumes: 无（独立组件）。
- Produces:
  - `src.core.tracing.TraceRecorder` 类 + 全局单例 `tracer`
  - `tracer.begin_run(route) -> None` / `end_run()`（二者之间为一次「当前运行」）
  - `record_node(node, status, duration_ms, detail="")`、`record_tool(tool, status)`、`record_tokens(n)`、`record_fallback(label="")`
  - `get_last_run() -> dict | None`、`recent_runs(n) -> list[dict]`
  - 运行结构：`{"route", "nodes": [...], "tools": [...], "tokens": int, "fallbacks": [...]}`

- [ ] **Step 1: 写失败测试 `tests/test_tracing.py`**

```python
# -*- coding: utf-8 -*-
from src.core.tracing import TraceRecorder


def _fresh():
    r = TraceRecorder()
    r.begin_run("email.refresh")
    return r


def test_record_and_last_run():
    r = _fresh()
    r.record_node("fetch", "ok", 12.0)
    r.record_tool("fetch_emails", "ok")
    r.record_tokens(150)
    r.end_run()
    run = r.get_last_run()
    assert run["route"] == "email.refresh"
    assert len(run["nodes"]) == 1
    assert run["nodes"][0]["node"] == "fetch"
    assert run["tokens"] == 150


def test_no_current_run_is_noop():
    r = TraceRecorder()
    r.record_tokens(10)  # 未 begin_run，不应崩
    r.record_node("n", "ok", 1.0)
    assert r.get_last_run() is None


def test_recent_runs_bounded():
    r = TraceRecorder(recent_maxlen=2)
    for i in range(3):
        r.begin_run(f"r{i}")
        r.end_run()
    assert len(r.recent_runs(10)) == 2
    assert r.recent_runs(1)[0]["route"] == "r2"
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_tracing.py
```
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 创建 `src/core/tracing.py`**

```python
# -*- coding: utf-8 -*-
"""执行观测：记录图执行轨迹、工具调用审计、token 用量。

进程内结构化缓冲，供可视化页展示（对应需求文档 6.3 审计日志）。
begin_run()/end_run() 之间为一次「当前运行」，record_* 写入当前运行；
未 begin_run 时 record_* 为 no-op，保证调用方无需判空。
"""
from collections import deque
from time import perf_counter


class TraceRecorder:
    def __init__(self, recent_maxlen: int = 200) -> None:
        self._recent_maxlen = recent_maxlen
        self._runs: deque[dict] = deque(maxlen=recent_maxlen)
        self._current: dict | None = None

    # ---------- 运行生命周期 ----------
    def begin_run(self, route: str) -> None:
        self._current = {
            "route": route,
            "nodes": [],
            "tools": [],
            "tokens": 0,
            "fallbacks": [],
        }

    def end_run(self) -> None:
        if self._current is not None:
            self._runs.append(self._current)
        self._current = None

    # ---------- 记录 ----------
    def record_node(self, node: str, status: str, duration_ms: float, detail: str = "") -> None:
        if self._current is None:
            return
        self._current["nodes"].append({
            "node": node, "status": status, "duration_ms": round(duration_ms, 1), "detail": detail,
        })

    def record_tool(self, tool: str, status: str) -> None:
        if self._current is None:
            return
        self._current["tools"].append({"tool": tool, "status": status})

    def record_tokens(self, n: int) -> None:
        if self._current is None:
            return
        self._current["tokens"] += int(n)

    def record_fallback(self, label: str = "") -> None:
        if self._current is None:
            return
        self._current["fallbacks"].append(label)

    # ---------- 查询 ----------
    def get_last_run(self) -> dict | None:
        return self._runs[-1] if self._runs else None

    def recent_runs(self, n: int) -> list[dict]:
        return list(self._runs)[-n:]


# 全局单例
tracer = TraceRecorder()
```

（`TraceRecorder(recent_maxlen=200)` 默认与 yaml 一致；Task 9 可视情况改为读 `config.TRACING_RECENT_MAXLEN`。）

- [ ] **Step 4: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 23 + 3 = 26 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: task 4 - trace recorder for execution/tool/token observability"
```

---

### Task 5: llm.py + classifier LLM 改造

**Files:**
- Create: `src/core/llm.py`、`tests/test_llm.py`
- Modify: `src/capabilities/email/classifier.py`（LLM 调用走 `src.core.llm`）
- Test: `tests/test_llm.py`（新增）

**Interfaces:**
- Consumes: `src.core.config_manager.config`（LLM_MODE/LLM_MODEL/LLM_BASE_URL/LLM_API_KEY/LLM_TEMPERATURE）；`src.core.tracing.tracer`（Task 4）。
- Produces:
  - `src.core.llm.LLMError`、`completion(messages, *, model=None, temperature=None, **kwargs) -> str`
  - `invoke_with_fallback(primary, fallback, *, label="") -> Any`

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**

```python
# -*- coding: utf-8 -*-
import pytest

from src.core.config_manager import config
from src.core.llm import LLMError, completion, invoke_with_fallback


def test_invoke_with_fallback_on_error():
    def boom():
        raise RuntimeError("llm down")

    got = invoke_with_fallback(boom, lambda e: "fallback-result", label="t")
    assert got == "fallback-result"


def test_invoke_with_fallback_primary_success():
    assert invoke_with_fallback(lambda: "ok", lambda e: "nope") == "ok"


def test_completion_requires_real_mode(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODE", "mock")
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    with pytest.raises(LLMError):
        completion([{"role": "user", "content": "hi"}])
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_llm.py
```
Expected: FAIL（`No module named 'src.core.llm'`）。

- [ ] **Step 3: 创建 `src/core/llm.py`**

```python
# -*- coding: utf-8 -*-
"""LLM 统一调用层。

completion() 封装 litellm（配置取自 config_manager），成功后把 token 用量
记录到 tracing；invoke_with_fallback 提供「主调用失败 → 兜底」容灾。
"""
from typing import Any, Callable

from src.core.config_manager import config
from src.core.logger import logger
from src.core.tracing import tracer


class LLMError(Exception):
    """LLM 调用失败（未配置或底层错误）。"""


def completion(messages: list[dict], *, model: str | None = None,
               temperature: float | None = None, **kwargs: Any) -> str:
    """调用 LLM 并返回文本内容。model/base_url/api_key 缺省取 config。"""
    if not (config.LLM_MODE == "real" and config.LLM_API_KEY):
        raise LLMError("LLM 未配置（LLM_MODE != real 或缺 API_KEY）")

    import litellm

    call_kwargs: dict[str, Any] = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
    }
    if config.LLM_BASE_URL:
        call_kwargs["api_base"] = config.LLM_BASE_URL
    if config.LLM_API_KEY:
        call_kwargs["api_key"] = config.LLM_API_KEY

    response = litellm.completion(**call_kwargs)
    content = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    total = getattr(usage, "total_tokens", None)
    if total:
        tracer.record_tokens(int(total))
    return content


def invoke_with_fallback(primary: Callable[[], Any], fallback: Callable[[Exception], Any],
                         *, label: str = "") -> Any:
    """primary() 成功返回其结果；抛异常则记录 fallback 并返回 fallback(exc)。"""
    try:
        return primary()
    except Exception as e:
        tracer.record_fallback(label or "fallback")
        logger.warning("core.llm", f"主调用失败，启用兜底{('（' + label + '）') if label else ''}: {e}")
        return fallback(e)
```

- [ ] **Step 4: 改 `classifier.py` 用 core.llm**

`_llm_completion_text(text, system_prompt)` 改为：
```python
from src.core.llm import completion, invoke_with_fallback

def _llm_classify(text: str, system_prompt: str) -> Classification:
    content = completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
    )
    raw = _parse_json(content)
    return Classification(
        urgency=raw.get("urgency", "普通"),
        action=raw.get("action", "仅需阅读"),
        category_tag=str(raw.get("category_tag", "") or "其他"),
        reason=str(raw.get("reason", "") or ""),
    )


def _safe_classify(text: str, system_prompt: str) -> Classification:
    """LLM 优先；任何失败退回规则分类。"""
    def _fallback(exc: Exception) -> Classification:
        logger.warning("email.classifier", f"LLM 分类失败，退回规则分类: {exc}")
        return _mock_classify(text)
    return invoke_with_fallback(lambda: _llm_classify(text, system_prompt), _fallback, label="classify")
```

`classify_one` 改为：
```python
def classify_one(self, email: Email) -> Classification:
    text = f"主题：{email.subject}\n正文：{email.body_preview}"[:_CLASSIFY_TEXT_LEN]
    if not self._config.llm_configured:
        return _mock_classify(text)
    return _safe_classify(text, self._config.get_prompt("email.classification"))
```
删除原 `_llm_classify` 中的 litellm 直接调用与重复封装；`_parse_json` 保留在 classifier。

- [ ] **Step 5: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 26 + 3 = 29 passed。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: task 5 - central LLM client with fallback, classifier uses it"
```

---

### Task 6: route 命名空间 + router.py + state capability

**Files:**
- Create: `src/core/router.py`、`tests/test_router.py`
- Modify: `src/core/state.py`（新增 `capability`）、`src/core/orchestrator.py`（`route_map()` 生成命名空间 key）、`src/capabilities/email/manifest.py`（`ROUTES = ["refresh"]`）、`tests/test_graph.py`、`tests/test_email_graph.py`、`tests/test_orchestrator.py`（route 字符串更新）
- Test: `tests/test_router.py`（新增）

**Interfaces:**
- Consumes: `orchestrator.route_map()`；Task 1 的 `src.core.graph.route_path`（valid_targets 钳制保留）。
- Produces:
  - 命名空间 route：`email.refresh`（manifest 声明裸 `"refresh"`，orchestrator 以 `f"{skill.name}.{route}"` 前缀）
  - `src.core.router.resolve(route: str) -> str | None`
  - `AgentState` 新增 `capability: str`

- [ ] **Step 1: 写失败测试 `tests/test_router.py`**

```python
# -*- coding: utf-8 -*-
import pytest

from src.core.orchestrator import orchestrator


@pytest.fixture(autouse=True)
def _scanned(mock_env):
    orchestrator.scan()
    yield


def test_resolve_hit():
    from src.core.router import resolve
    assert resolve("email.refresh") == "email"


def test_resolve_miss():
    from src.core.router import resolve
    assert resolve("nonsense") is None
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_router.py
```
Expected: FAIL（`resolve` 不存在；或 `resolve("email.refresh")` 返回 None，因 route_map 尚无命名空间）。

- [ ] **Step 3: 改 `src/core/state.py`**

```python
class AgentState(TypedDict, total=False):
    route: str                  # 命名空间 route，如 "email.refresh"
    request: dict[str, Any]     # 请求参数
    capability: str             # 本次执行的能力名（如 "email"）
    emails: list[Email]         # 拉取结果（类型化，Task 2）
    classified: list[EmailClassified]
    messages: list[dict]        # 会话历史（Phase 2 启用）
    errors: list[str]           # 错误收集
```
（import：`from src.core.schemas import Email, EmailClassified`。）

- [ ] **Step 4: 改 `orchestrator.py` 的 `route_map()`**

```python
def route_map(self) -> dict[str, str]:
    """{命名空间 route: 能力节点名}，如 {"email.refresh": "email"}。技能名唯一 → 天然不撞名。"""
    return {
        f"{skill.name}.{route}": skill.name
        for skill in self._skills
        for route in skill.routes
    }
```

- [ ] **Step 5: 改 `manifest.py`**

```python
# 本能力子图可处理的裸 route 名；orchestrator 会以前缀生成 "email.refresh"
ROUTES = ["refresh"]
```

- [ ] **Step 6: 创建 `src/core/router.py`**

```python
# -*- coding: utf-8 -*-
"""路由解析：命名空间 route → 能力节点名。

当前由 route 表直接分发；Phase 2 演进为 LLM 意图分类（对应 supervisor.py），
resolve 接口保持 resolve(request) -> route。
"""
from src.core.orchestrator import orchestrator


def resolve(route: str) -> str | None:
    """返回 route 对应的能力节点名；未命中返回 None（超级图退化为 END）。"""
    return orchestrator.route_map().get(route)
```

- [ ] **Step 7: 更新既有测试的 route 字符串**

`refresh_email` → `email.refresh`，出现在：
- `tests/test_graph.py`：`test_agent_refresh_email_flow` 的 `{"route": "refresh_email"}` → `"email.refresh"`；`test_route_path_degrades_unbuilt_skill` 的 monkeypatch route_map 键改为 `{"email.refresh": "email", "broken.refresh": "broken_skill"}`；`test_agent_invoke_degrades_unbuilt_skill` 同理（route 用 `"broken.refresh"`）。
- `tests/test_email_graph.py`：若断言含 `"refresh_email"` → `"email.refresh"`。
- `tests/test_orchestrator.py`：`route_map()` 断言改为命名空间 key（如 `{"email.refresh": "email"}`）。

（`test_agent_unknown_route_ends` 用 `"nonsense"` 不变。）

- [ ] **Step 8: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 29 + 2 = 31 passed。

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: task 6 - namespaced routes (email.refresh) + router.resolve + state.capability"
```

---

### Task 7: orchestrator 契约校验

**Files:**
- Modify: `src/core/orchestrator.py`（`_load_skill` 加契约校验）
- Test: `tests/test_orchestrator.py`（新增校验用例）

**Interfaces:**
- Consumes: `ToolDefinition`（`tool_type` 合法性由其 `__post_init__` 保证）。
- Produces: `_validate_manifest(module, skill_name) -> list[str]`；违规 → `SkillInfo.status="error"` + 明确 `error` 文案。

- [ ] **Step 1: 写失败测试（追加到 `tests/test_orchestrator.py`）**

```python
def test_manifest_missing_route_subgraph_is_error(tmp_path):
    """ROUTES 非空但缺 build_subgraph → status=error，且不阻塞其他能力。"""
    from src.core.orchestrator import Orchestrator

    d = tmp_path / "broken"
    d.mkdir()
    (d / "manifest.py").write_text(
        "SKILL_META = {'name': 'broken'}\nROUTES = ['x']\n", encoding="utf-8"
    )
    o = Orchestrator()
    skills = o.scan(tmp_path)
    broken = next(s for s in skills if s.name == "broken")
    assert broken.status == "error"
    assert "build_subgraph" in broken.error


def test_manifest_missing_meta_name_is_error(tmp_path):
    d = tmp_path / "noname"
    d.mkdir()
    (d / "manifest.py").write_text("ROUTES = []\n", encoding="utf-8")
    o = Orchestrator()
    skills = o.scan(tmp_path)
    bad = next(s for s in skills if s.name == "noname")
    assert bad.status == "error"
    assert "name" in bad.error
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_orchestrator.py
```
Expected: FAIL（两个新用例，现状不校验）。

- [ ] **Step 3: 改 `orchestrator.py`**

在 `_load_skill` 内、import 成功后、加载字段前，先校验：
```python
problems = self._validate_manifest(module, skill_name)
if problems:
    raise ValueError("manifest 契约不合法: " + "；".join(problems))
```
新增方法：
```python
@staticmethod
def _validate_manifest(module, skill_name: str) -> list[str]:
    """返回 manifest 契约违规列表（空 = 合法）。"""
    problems: list[str] = []
    meta = getattr(module, "SKILL_META", {})
    if not isinstance(meta, dict) or not meta.get("name"):
        problems.append("SKILL_META.name 缺失或非法")

    get_tools = getattr(module, "get_tools", None)
    if callable(get_tools):
        try:
            defs = list(get_tools())
        except Exception as e:
            problems.append(f"get_tools() 抛错: {e}")
            defs = []
        for d in defs:
            if not hasattr(d, "name") or not hasattr(d, "tool_type"):
                problems.append("get_tools() 返回了非 ToolDefinition 元素")

    routes = getattr(module, "ROUTES", [])
    if routes:
        if not all(isinstance(r, str) for r in routes):
            problems.append("ROUTES 必须是 str 列表")
        if not callable(getattr(module, "build_subgraph", None)):
            problems.append("ROUTES 非空但缺 build_subgraph()")

    return problems
```
（`_load_skill` 的现有 `try/except` 会把 `ValueError` 记入 `status="error"`，无需额外处理。）

- [ ] **Step 4: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 31 + 2 = 33 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: task 7 - orchestrator manifest contract validation"
```

---

### Task 8: checkpointer 抽象

**Files:**
- Create: `src/core/checkpointer.py`
- Modify: `src/core/graph.py`（不再直接 import MemorySaver）

**Interfaces:**
- Consumes: 无。
- Produces: `src.core.checkpointer.build_checkpointer()`，返回可编译进 LangGraph 的 checkpointer（现为 `MemorySaver()`）。

**步骤：**

- [ ] **Step 1: 创建 `src/core/checkpointer.py`**

```python
# -*- coding: utf-8 -*-
"""会话持久化抽象。

当前使用内存 MemorySaver；后续可替换为 Postgres checkpoint（对应
gaokao_tutor 参考的 src/database/checkpointer.py），接口不变。
"""
def build_checkpointer():
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
```

- [ ] **Step 2: 改 `graph.py`**

- 删除 `from langgraph.checkpoint.memory import MemorySaver`。
- 新增 `from src.core.checkpointer import build_checkpointer`。
- `compile(checkpointer=MemorySaver())` → `compile(checkpointer=build_checkpointer())`。

- [ ] **Step 3: 全量测试（回归验证图仍可编译/执行）**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 33 passed。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: task 8 - abstract checkpointer factory"
```

---

### Task 9: 节点包装 + 工具审计 + visualizer + 可视化页 + main 指标

**Files:**
- Modify: `src/core/tracing.py`（加 `@traced` 装饰器）、`src/core/safety.py`（`safe_call` 记录工具审计）、`src/capabilities/email/graph.py`（节点包 `@traced`）、`src/capabilities/email/ui_page.py`（invoke 前后 `begin_run/end_run`）、`src/core/visualizer.py`（新增）、`main.py`（会话消息指标 → tracing 指标）
- Create: `pages/01_可视化.py`
- Rename: `pages/01_邮件处理.py` → `pages/02_邮件处理.py`
- Test: `tests/test_tracing.py`（新增 `@traced` 用例）

**Interfaces:**
- Consumes: Task 4 的 `tracer`；`safe_call`（`src.core.safety`）；`config.TRACING_ENABLED`。
- Produces:
  - `src.core.tracing.traced(fn)` 装饰器（计时 + `record_node`）
  - `src.core.visualizer.render_graph_svg(nodes, edges, executed) -> str`
  - `pages/01_可视化.py`、`pages/02_邮件处理.py`

- [ ] **Step 1: 写失败测试（追加到 `tests/test_tracing.py`）**

```python
def test_traced_decorator_records_node():
    from src.core.tracing import TraceRecorder, traced

    r = TraceRecorder()
    r.begin_run("email.refresh")

    @traced(target=r)
    def fetch_node(state):
        return {"emails": []}

    fetch_node({})
    r.end_run()
    run = r.get_last_run()
    assert run["nodes"][0]["node"] == "fetch_node"
    assert run["nodes"][0]["status"] == "ok"
```

- [ ] **Step 2: 运行确认失败**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest tests/test_tracing.py
```
Expected: FAIL（`traced` 不存在）。

- [ ] **Step 3: 改 `tracing.py` 加 `@traced`**

放在 `tracer = TraceRecorder()` 之后（`traced` 定义于 `tracer` 之后，默认参数直接引用模块全局 `tracer`，无定义期问题、无 `globals()` 取巧）：

```python
from functools import wraps
from time import perf_counter


def traced(*, target: "TraceRecorder | None" = None):
    """包裹图节点：计时并记录执行轨迹。缺省记录到全局 tracer。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(state):
            rec = target if target is not None else tracer
            start = perf_counter()
            result = fn(state)
            duration_ms = (perf_counter() - start) * 1000
            if rec is not None:
                status = "error" if (result or {}).get("errors") else "ok"
                rec.record_node(fn.__name__, status, duration_ms)
            return result
        return wrapper
    return decorator
```

- [ ] **Step 4: 改 `safety.py` 的 `safe_call` 记录工具审计**

```python
from src.core.tracing import tracer
...
def safe_call(tool_name: str, **kwargs: Any) -> Any:
    definition = registry.get_tool(tool_name)
    if definition is None:
        tracer.record_tool(tool_name, "unknown")
        raise PermissionDeniedError(f"未注册工具: {tool_name}")
    verdict = gateway.check_permission(tool_name)
    if verdict == PERMIT_DENIED:
        tracer.record_tool(tool_name, "denied")
        raise PermissionDeniedError(f"工具被安全网关拒绝: {tool_name}")
    if verdict == PERMIT_NEEDS_CONFIRM:
        tracer.record_tool(tool_name, "needs_confirm")
        raise NeedsConfirmError(f"工具需要用户确认: {tool_name}")
    try:
        result = definition.handler(**kwargs)
    except Exception:
        tracer.record_tool(tool_name, "error")
        raise
    tracer.record_tool(tool_name, "ok")
    return result
```

- [ ] **Step 5: 改 `email/graph.py` 节点包 `@traced`**

```python
from src.core.tracing import traced

@traced()
def fetch_node(state: AgentState) -> dict:
    ...

@traced()
def classify_node(state: AgentState) -> dict:
    ...
```

- [ ] **Step 6: 改 `ui_page.py` 的 `_refresh()` 记录一次运行**

```python
from src.core.tracing import tracer

def _refresh() -> None:
    from src.core.graph import agent

    with st.spinner("正在拉取并分类邮件..."):
        tracer.begin_run("email.refresh")
        try:
            result = agent.invoke(
                {"route": "email.refresh"},
                config={"configurable": {"thread_id": "ui"}},
            )
            ...
        except Exception as e:
            ...
        finally:
            tracer.end_run()
    st.rerun()
```
（route 同步改为 `"email.refresh"`。）

- [ ] **Step 7: 创建 `src/core/visualizer.py`**

```python
# -*- coding: utf-8 -*-
"""图结构 SVG 渲染（零依赖）。

节点为矩形盒、边为箭头；已执行节点绿色高亮并标耗时。
供 Streamlit 经 st.components.v1.html 展示。
"""


def _layers(nodes: list[dict], edges: list[tuple[str, str]]) -> dict[str, int]:
    """按拓扑分层：source 层 < target 层。"""
    layer = {node["name"]: 0 for node in nodes}
    changed = True
    while changed:
        changed = False
        for src, dst in edges:
            if layer.get(src, 0) + 1 > layer.get(dst, 0):
                layer[dst] = layer[src] + 1
                changed = True
    return layer


def render_graph_svg(nodes: list[dict], edges: list[tuple[str, str]],
                     executed: dict[str, dict] | None = None) -> str:
    """渲染 DAG 为 SVG 字符串。

    nodes: [{"name": ..., "label": ...}]；edges: [(src, dst), ...]
    executed: {node_name: {"duration_ms": float, "status": str}}
    """
    executed = executed or {}
    layers = _layers(nodes, edges)
    box_w, box_h, gap_x, gap_y, margin = 150, 48, 60, 40, 20
    by_layer: dict[int, list[str]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node["name"]], []).append(node["name"])
    max_cols = max(len(v) for v in by_layer.values())
    pos: dict[str, tuple[int, int]] = {}
    for name, lst in by_layer.items():
        for i, node_name in enumerate(lst):
            pos[node_name] = (
                margin + layers[node_name] * (box_w + gap_x),
                margin + i * (box_h + gap_y),
            )
    max_layer = max(layers.values())
    width = margin * 2 + (max_layer + 1) * box_w + max_layer * gap_x
    height = margin * 2 + max_cols * box_h + (max_cols - 1) * gap_y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
        'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#666"/></marker></defs>',
    ]
    for src, dst in edges:
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        parts.append(
            f'<line x1="{x1 + box_w}" y1="{y1 + box_h // 2}" x2="{x2}" y2="{y2 + box_h // 2}" '
            'stroke="#999" stroke-width="1.5" marker-end="url(#arrow)"/>'
        )
    for node in nodes:
        x, y = pos[node["name"]]
        ex = executed.get(node["name"])
        fill = "#d4edda" if ex else "#f8f9fa"
        stroke = "#1e7e34" if ex else "#adb5bd"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + box_w // 2}" y="{y + 22}" text-anchor="middle" font-size="13" '
            f'font-weight="bold">{node["label"]}</text>'
        )
        if ex:
            parts.append(
                f'<text x="{x + box_w // 2}" y="{y + 40}" text-anchor="middle" font-size="11" '
                f'fill="#1e7e34">{ex.get("duration_ms", 0):.1f} ms · {ex.get("status", "")}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)
```

- [ ] **Step 8: 创建 `pages/01_可视化.py`**

```python
# -*- coding: utf-8 -*-
"""图执行可视化页：图结构 DAG + 最近执行轨迹 + token/工具审计 + 日志。"""
import streamlit as st

from src.core.logger import logger
from src.core.orchestrator import orchestrator
from src.core.tracing import tracer
from src.core.visualizer import render_graph_svg

st.set_page_config(page_title="图可视化", page_icon="📊", layout="wide")
st.title("📊 图执行可视化")

orchestrator.get_all_skills()

NODES = [
    {"name": "route", "label": "route\n入口"},
    {"name": "email.fetch", "label": "email.fetch\n拉取"},
    {"name": "email.classify", "label": "email.classify\n分类"},
]
EDGES = [("route", "email.fetch"), ("email.fetch", "email.classify")]

run = tracer.get_last_run()
executed = {n["node"]: n for n in run["nodes"]} if run else {}
svg = render_graph_svg(NODES, EDGES, executed)
st.subheader("图结构（已执行节点高亮）")
st.components.v1.html(svg, height=220)

st.subheader("最近一次执行")
if run:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("route", run["route"])
    c2.metric("节点数", len(run["nodes"]))
    c3.metric("token 用量", run["tokens"])
    c4.metric("兜底次数", len(run["fallbacks"]))
    st.caption("节点轨迹")
    st.dataframe(run["nodes"], use_container_width=True)
    if run["tools"]:
        st.caption("工具调用审计")
        st.dataframe(run["tools"], use_container_width=True)
else:
    st.info("尚无执行记录。去「📧 智能邮件处理」页点一次刷新即可看到。")

st.subheader("最近日志")
for line in logger.recent(15):
    st.code(line)
```

- [ ] **Step 9: 重命名邮件页**

```bash
git mv "pages/01_邮件处理.py" "pages/02_邮件处理.py"
```
内容不变（其 import 在 Task 1 已更新为 `src.capabilities.email.ui_page`）。

- [ ] **Step 10: 改 `main.py` 指标**

把「会话消息」死指标替换为 tracing 指标：
```python
from src.core.tracing import tracer
...
run = tracer.get_last_run()
c4.metric("最近执行", run["route"] if run else "—")
```
删除 `agent.get_state` 那段 try/except 与 `_msg_count`（若 `agent` 导入因此不再被 main.py 使用，则删除 `from src.core.graph import agent` 行）。

- [ ] **Step 11: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 33 + 1 = 34 passed（`test_pages.py` 的 AppTest 页路径如有变化按实际文件名同步）。

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "feat: task 9 - execution visualization (tracing@nodes, safe_call audit, SVG viz page)"
```

---

### Task 10: 全量回归 + README 结构更新 + 真实模式验证

**Files:**
- Modify: `README.md`（目录结构段更新为 src/ 布局 + 新增可视化说明）
- Test: 全量；随后真实模式验证

**步骤：**

- [ ] **Step 1: 更新 `README.md` 结构段**

按新目录结构重写「项目结构」小节（含 `src/core/`、`src/capabilities/`、`config/settings.yaml`、`config/prompts/`、`pages/01_可视化.py`），说明「能力插件机制」与「可视化页」。

- [ ] **Step 2: 全量测试**

```bash
D:/conda_envs/GM-Assistant/python.exe -m pytest
```
Expected: 34 passed。

- [ ] **Step 3: 真实模式验证（不 Mock）**

确认 `.env` 存在（IMAP 凭据 + `LLM_MODE=real` + API Key）。临时以真实配置运行一次分类：
```bash
D:/conda_envs/GM-Assistant/python.exe -c "
from src.core.graph import agent
r = agent.invoke({'route': 'email.refresh'}, config={'configurable': {'thread_id': 'real-check'}})
print('route =', r.get('route'), '| emails =', len(r.get('emails') or []), '| classified =', len(r.get('classified') or []))
"
```
Expected: 与重构前一致（拉取 N 封、全部分类，N≈邮箱实际未读数）。同时确认：
- `safe_call` 审计已写入（可选：跑一次 `src.core.tracing` 断言 `tracer.get_last_run()` 非空）。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: task 10 - README structure for src layout + visualization"
```

---

## 自审

- **Spec 覆盖**：设计文档 4.1~4.9 均已落到 Task 1~10（包结构→T1；schemas→T2；config/prompt→T3；tracing recorder→T4；llm→T5；route/router/state→T6；契约校验→T7；checkpointer→T8；节点包装/审计/可视化/main 指标→T9；回归/README/真实验证→T10）。
- **占位符扫描**：无 TBD/TODO；所有代码步骤为完整可执行内容。
- **类型一致性**：`Email`/`Classification`/`EmailClassified` 签名在 T2~T9 一致；`resolve(route)` 返回类型一致；`route_map` 命名空间 key 在 T6 起一致；`tracer` 单例在 T4/T5/T9 一致引用。
