# -*- coding: utf-8 -*-
"""统一日志模块。

- 统一格式：[时间] [模块] [级别] 消息
- 输出到控制台与日志文件（路径默认 logs/agent.log）
- 敏感信息脱敏：遮蔽邮箱地址与密码/密钥类字段值
- 维护近期日志缓冲，供首页展示
- 安全约定：邮件正文内容一律不写入日志，只记录 ID 与元数据
"""
import re
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

# Windows 控制台默认 cp936，统一改为 UTF-8 输出，避免中文日志乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 项目根目录下 logs/ 作为默认日志目录
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_DEFAULT_LOG_FILE = _LOG_DIR / "agent.log"

# 邮箱地址
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 密码 / 密钥类字段（key=value 形式）
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|password|passwd|pwd|secret|token|authorization|access[_-]?token)"
    r"\s*[=:：]\s*\S+"
)


def redact(text: str) -> str:
    """对文本做脱敏：遮蔽邮箱地址与密码/密钥类字段值。"""
    def _mask_email(match: re.Match) -> str:
        local, _, domain = match.group(0).partition("@")
        return f"{local[:1]}***@{domain}"

    text = _EMAIL_RE.sub(_mask_email, text)
    text = _SECRET_RE.sub(lambda m: f"{m.group(1)}=***", text)
    return text


class AgentLogger:
    """统一日志：格式 [时间] [模块] [级别] 消息。"""

    def __init__(self, log_file: str | Path | None = None, recent_maxlen: int = 200) -> None:
        self._log_file = Path(log_file) if log_file else _DEFAULT_LOG_FILE
        self._recent: deque[str] = deque(maxlen=recent_maxlen)
        self._console = True
        self._file_handle = None
        if self._log_file:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(self._log_file, "a", encoding="utf-8")

    def _emit(self, level: str, module: str, msg: str) -> None:
        """写入一条日志（统一脱敏后）。"""
        safe = redact(str(msg))
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{module}] [{level}] {safe}"
        self._recent.append(line)
        if self._console:
            print(line)
        if self._file_handle:
            self._file_handle.write(line + "\n")
            self._file_handle.flush()

    def debug(self, module: str, msg: str) -> None:
        self._emit("DEBUG", module, msg)

    def info(self, module: str, msg: str) -> None:
        self._emit("INFO", module, msg)

    def warning(self, module: str, msg: str) -> None:
        self._emit("WARN", module, msg)

    def error(self, module: str, msg: str) -> None:
        self._emit("ERROR", module, msg)

    def recent(self, n: int = 30) -> list[str]:
        """返回最近 n 条日志（供首页展示）。"""
        return list(self._recent)[-n:]


# 全局单例
logger = AgentLogger()
