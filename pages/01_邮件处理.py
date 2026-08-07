# -*- coding: utf-8 -*-
"""邮件处理页：极简转发到 skills.email.ui_page。

Streamlit 根据 pages/ 目录自动发现本页面；所有界面逻辑集中在技能模块内，
保持主项目与技能模块解耦。
"""
from skills.email.ui_page import render

render()
