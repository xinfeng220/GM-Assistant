# -*- coding: utf-8 -*-
"""邮件处理页：极简转发到 src.capabilities.email.ui_page。

Streamlit 根据 pages/ 目录自动发现本页面；所有界面逻辑集中在能力模块内，
保持主项目与能力模块解耦。
"""
from src.capabilities.email.ui_page import render

render()
