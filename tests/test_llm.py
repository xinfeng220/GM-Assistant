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
