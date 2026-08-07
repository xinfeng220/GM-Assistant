# -*- coding: utf-8 -*-
# NOTE: 构造时用 **{"from": ...} 传递别名键（"from" 是 Python 关键字，
# 不能直接写 Email(from="...")）；与 _fetch_mock 的 Email(**m) 走同一路径。
from src.core.schemas import Classification, Email, EmailClassified


def test_classification_normalizes_bad_urgency():
    c = Classification(urgency="不存在的级别", action="需要回复")
    assert c.urgency == "普通"


def test_classification_normalizes_bad_action():
    c = Classification(urgency="紧急", action="不存在的动作")
    assert c.action == "仅需阅读"


def test_email_accepts_from_alias():
    e = Email(**{"id": "1", "from": "x@y.com", "subject": "你好"})
    assert e.from_ == "x@y.com"
    assert e.model_dump(by_alias=True)["from"] == "x@y.com"


def test_email_classified_roundtrip():
    ec = EmailClassified(**{"id": "1", "from": "a@b.com"}, classification=Classification(urgency="紧急", action="需要回复"))
    d = ec.model_dump(by_alias=True)
    assert d["from"] == "a@b.com"
    assert d["classification"]["urgency"] == "紧急"
