# -*- coding: utf-8 -*-
from pathlib import Path

from streamlit.testing.v1 import AppTest

# AppTest.from_file() 相对路径以调用方文件所在目录为基准，故用项目根目录锚定
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_email_page_refresh_renders_groups(mock_env):
    at = AppTest.from_file(_PROJECT_ROOT / "pages/01_邮件处理.py", default_timeout=30)
    at.run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception
    assert len(at.expander) >= 1  # 至少渲染出邮件展开器


def test_overview_page_renders(mock_env):
    at = AppTest.from_file(_PROJECT_ROOT / "main.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.metric) >= 3    # 技能模块 / 工具注册 / 安全模式
