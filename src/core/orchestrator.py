# -*- coding: utf-8 -*-
"""技能编排器。

启动时扫描 src/capabilities/ 目录下所有子目录，寻找 manifest.py 并动态加载：
- 收集技能元信息
- 注册技能声明的工具到统一工具注册中心
- 单个技能加载失败不影响其他技能
"""
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import logger
from src.core.tool_registry import registry

# 能力目录：项目根/src/capabilities
_SKILLS_DIR = Path(__file__).resolve().parents[1] / "capabilities"


@dataclass
class SkillInfo:
    """已加载技能的元信息。"""

    name: str
    title: str = ""
    description: str = ""
    version: str = ""
    status: str = "unknown"   # active / not_configured / error
    path: Path | None = None
    tools: list[str] = field(default_factory=list)
    hint: str = ""            # 配置提示（如 Mock 模式）
    routes: list[str] = field(default_factory=list)  # 本技能子图可处理的 route
    subgraph: object | None = None                   # 编译后的 LangGraph 子图
    error: str = ""


class Orchestrator:
    """扫描并加载所有技能模块。"""

    def __init__(self) -> None:
        self._skills: list[SkillInfo] = []
        self._scanned = False

    def scan(self, skills_dir: str | Path | None = None) -> list[SkillInfo]:
        """扫描 src/capabilities/ 下每个含 manifest.py 的子目录并加载。"""
        skills_dir = Path(skills_dir) if skills_dir else _SKILLS_DIR
        self._skills = []
        registry.clear()  # 重新扫描时重置注册中心，避免残留

        if not skills_dir.is_dir():
            logger.warning("orchestrator", f"capabilities 目录不存在: {skills_dir}")
            self._scanned = True
            return self._skills

        manifests = sorted(skills_dir.glob("*/manifest.py"))
        for manifest_path in manifests:
            self._load_skill(manifest_path)

        self._scanned = True
        logger.info(
            "orchestrator",
            f"扫描完成，共加载 {len(self._skills)} 个技能、{registry.count()} 个工具",
        )
        return self._skills

    def _load_skill(self, manifest_path: Path) -> None:
        """加载单个技能，失败仅标记 error，不阻塞整体。"""
        skill_name = manifest_path.parent.name
        info = SkillInfo(name=skill_name, path=manifest_path.parent)
        try:
            module = self._import_module(manifest_path, f"skill_{skill_name}")

            problems = self._validate_manifest(module, skill_name)
            if problems:
                raise ValueError("manifest 契约不合法: " + "；".join(problems))

            meta = getattr(module, "SKILL_META", {})
            info.title = meta.get("title", skill_name)
            info.description = meta.get("description", "")
            info.version = meta.get("version", "")

            get_tools = getattr(module, "get_tools", None)
            if callable(get_tools):
                for definition in get_tools():
                    registry.register_tool(definition)
                    info.tools.append(definition.name)
                    logger.info(
                        "orchestrator",
                        f"注册工具 [{definition.name}]（{definition.tool_type}）← 技能 {skill_name}",
                    )

            get_status = getattr(module, "get_status", None)
            info.status = get_status() if callable(get_status) else "active"

            get_hint = getattr(module, "get_config_hint", None)
            info.hint = get_hint() if callable(get_hint) else ""

            routes = getattr(module, "ROUTES", [])
            info.routes = list(routes)

            build_subgraph = getattr(module, "build_subgraph", None)
            if callable(build_subgraph):
                info.subgraph = build_subgraph()

            logger.info("orchestrator", f"加载技能 [{skill_name}] 成功，状态={info.status}")
        except Exception as e:  # 单个技能失败不阻塞其他技能
            info.status = "error"
            info.error = str(e)
            logger.error("orchestrator", f"加载技能 [{skill_name}] 失败: {e}")

        self._skills.append(info)

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

    @staticmethod
    def _import_module(path: Path, module_name: str):
        """从文件路径动态加载一个 Python 模块。"""
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法解析模块文件: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def get_all_skills(self) -> list[SkillInfo]:
        """返回已加载技能列表（尚未扫描则先扫描）。"""
        if not self._scanned:
            self.scan()
        return self._skills

    def route_map(self) -> dict[str, str]:
        """{命名空间 route: 能力节点名}，如 {"email.refresh": "email"}。技能名唯一 → 天然不撞名。"""
        return {
            f"{skill.name}.{route}": skill.name
            for skill in self._skills
            for route in skill.routes
        }


# 全局单例
orchestrator = Orchestrator()
