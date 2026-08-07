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
