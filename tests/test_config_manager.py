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
