# -*- coding: utf-8 -*-
"""Pydantic 类型化模型（工具边界契约）。

fetch_emails → list[Email]；classify_emails → list[EmailClassified]。
值域归一化在 field_validator 内做回退，等价于原 classifier._validate_result。
"""
from pydantic import BaseModel, Field, field_validator

URGENCY_LEVELS = ("紧急", "重要", "普通", "可忽略")
ACTIONS = ("需要回复", "仅需阅读", "可转交", "可归档")


class Classification(BaseModel):
    urgency: str
    action: str
    category_tag: str = "其他"
    reason: str = ""
    confidence: float | None = None  # Phase 2 LLM 置信度

    @field_validator("urgency")
    @classmethod
    def _norm_urgency(cls, v: str) -> str:
        return v if v in URGENCY_LEVELS else "普通"

    @field_validator("action")
    @classmethod
    def _norm_action(cls, v: str) -> str:
        return v if v in ACTIONS else "仅需阅读"


class Email(BaseModel):
    id: str
    subject: str = ""
    from_: str = Field(default="", alias="from")  # 对外序列化/构造仍用 "from"
    received_at: str = ""
    body_preview: str = ""

    model_config = {"populate_by_name": True}


class EmailClassified(Email):
    classification: Classification
