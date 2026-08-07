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
