# -*- coding: utf-8 -*-
"""邮件分类模块。

- LLM 模式（config.llm_configured 为 True）：经 litellm 调用真实模型，输出结构化 JSON
- Mock 模式（默认）：关键词规则分类，无需任何 API Key

每次分类仅传入「主题 + 正文前 500 字」，避免 token 浪费。
"""
import json
import re

from agent_core.logger import logger
from config import config
from skills.email.prompts.classification import SYSTEM_PROMPT

URGENCY_LEVELS = ("紧急", "重要", "普通", "可忽略")
ACTIONS = ("需要回复", "仅需阅读", "可转交", "可归档")

# 分类时截取的主题+正文长度上限
_CLASSIFY_TEXT_LEN = 500

# ---------------- Mock 关键词规则 ----------------
_URGENT_KEYWORDS = ("告警", "宕机", "故障", "紧急", "投诉", "升级", "立即", "尽快", "截止", "今日", "停机", "损失", "异常")
_IMPORTANT_KEYWORDS = ("审批", "预算", "合同", "汇报", "签署", "续约", "洽谈", "方案", "评审", "决策", "项目")
_IGNORABLE_KEYWORDS = ("newsletter", "订阅", "广告", "促销", "系统通知", "周报", "noreply", "no-reply", "验证码", "自动")
_REPLY_KEYWORDS = ("请回复", "望回复", "盼复", "请确认", "请答复", "是否", "麻烦", "请问", "回复我", "请示", "告知")
_FORWARD_KEYWORDS = ("汇报", "月报", "抄送", "请知悉", "备案", "同步", "纪要", "报表")


def _first_hit(keywords: tuple[str, ...], text: str) -> str | None:
    """返回第一个命中的关键词。"""
    for kw in keywords:
        if kw in text:
            return kw
    return None


def _mock_classify(text: str) -> dict:
    """基于关键词的规则分类（无需调用 LLM）。"""
    lower = text.lower()

    # 紧急度
    if _first_hit(_URGENT_KEYWORDS, lower):
        urgency = "紧急"
    elif _first_hit(_IGNORABLE_KEYWORDS, lower):
        urgency = "可忽略"
    elif _first_hit(_IMPORTANT_KEYWORDS, lower):
        urgency = "重要"
    else:
        urgency = "普通"

    # 动作
    hit_reply = _first_hit(_REPLY_KEYWORDS, lower)
    hit_forward = _first_hit(_FORWARD_KEYWORDS, lower)
    if hit_reply:
        action = "需要回复"
        reason = f"含请求性用语「{hit_reply}」"
    elif hit_forward:
        action = "可转交"
        reason = f"含汇报/知悉类用语「{hit_forward}」"
    elif urgency == "可忽略":
        action = "可归档"
        reason = "系统通知/订阅类，无需处理"
    else:
        action = "仅需阅读"
        reason = "信息同步类，无需回复"

    # 业务标签
    if any(k in lower for k in ("客户", "合同", "合作", "订单", "供应商", "报价")):
        tag = "客户-业务"
    elif urgency == "紧急":
        tag = "紧急事件"
    elif any(k in lower for k in ("审批", "预算", "汇报", "会议", "产品")):
        tag = "内部-管理"
    elif urgency == "可忽略":
        tag = "系统-通知"
    else:
        tag = "其他"

    return {
        "urgency": urgency,
        "action": action,
        "category_tag": tag,
        "reason": reason,
    }


# ---------------- LLM 路径（litellm） ----------------
def _llm_classify(text: str) -> dict:
    """经 litellm 调用真实模型分类；失败抛异常，由上层退回规则分类。"""
    import litellm

    kwargs: dict = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
    }
    if config.LLM_BASE_URL:
        kwargs["api_base"] = config.LLM_BASE_URL
    if config.LLM_API_KEY:
        kwargs["api_key"] = config.LLM_API_KEY

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    return _validate_result(_parse_json(content))


def _parse_json(content: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍 ```json 包裹或多余文字）。"""
    match = re.search(r"\{.*\}", content.strip(), re.S)
    if match:
        content = match.group(0)
    return json.loads(content)


def _validate_result(data: dict) -> dict:
    """校验并归一化分类结果，非法值回退到安全默认。"""
    urgency = data.get("urgency") if data.get("urgency") in URGENCY_LEVELS else "普通"
    action = data.get("action") if data.get("action") in ACTIONS else "仅需阅读"
    return {
        "urgency": urgency,
        "action": action,
        "category_tag": str(data.get("category_tag", "") or "其他"),
        "reason": str(data.get("reason", "") or ""),
    }


class EmailClassifier:
    """邮件分类器：LLM 优先，未配置或无 Key 时自动退回规则分类。"""

    def __init__(self) -> None:
        self._config = config

    def classify_one(self, email_item: dict) -> dict:
        """对单封邮件分类，返回 {urgency, action, category_tag, reason}。"""
        subject = email_item.get("subject", "")
        preview = email_item.get("body_preview", "")
        text = f"主题：{subject}\n正文：{preview}"[:_CLASSIFY_TEXT_LEN]

        if self._config.llm_configured:
            try:
                result = _llm_classify(text)
                logger.info("email.email_classifier", f"LLM 分类完成: {email_item.get('id')}")
                return result
            except Exception as e:
                # 真实模型调用失败时退回规则分类，保证页面可用
                logger.warning("email.email_classifier", f"LLM 分类失败，退回规则分类: {e}")

        return _mock_classify(text)

    def classify_many(self, emails: list[dict]) -> list[dict]:
        """批量分类，返回带 classification 字段的新列表。"""
        results = []
        for email_item in emails:
            results.append({**email_item, "classification": self.classify_one(email_item)})
        logger.info("email.email_classifier", f"批量分类完成，共 {len(results)} 封")
        return results


def classify_emails(emails: list[dict]) -> list[dict]:
    """技能对外工具：对邮件列表做批量分类。"""
    return EmailClassifier().classify_many(emails)


__all__ = ["EmailClassifier", "classify_emails", "URGENCY_LEVELS", "ACTIONS"]
