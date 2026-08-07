# -*- coding: utf-8 -*-
"""会话持久化抽象。

当前使用内存 MemorySaver；后续可替换为 Postgres checkpoint（对应
gaokao_tutor 参考的 src/database/checkpointer.py），接口不变。
"""
def build_checkpointer():
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
