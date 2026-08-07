# -*- coding: utf-8 -*-
"""邮件拉取模块。

通过 IMAP 拉取最近未读邮件，返回结构化 Email 列表；
未配置真实邮箱（config.imap_configured 为 False）时自动使用 Mock 样例数据，便于无凭据演示。

安全约定：邮件正文不写入日志，只记录数量与元数据；邮件内容仅在内存中处理。
"""
import email
import email.message
import imaplib
import re
from email.header import decode_header

from src.core.logger import logger
from src.core.config_manager import config
from src.core.schemas import Email

# ---------------- Mock 样例邮件（覆盖四档紧急度，便于演示） ----------------
_MOCK_EMAILS: list[dict] = [
    {
        "id": "mock-1",
        "subject": "【告警】线上支付服务异常，需立即处理",
        "from": "运维告警 <ops@company.com>",
        "received_at": "2026-08-06 09:15",
        "body_preview": (
            "线上支付服务自 09:10 起出现大量 5xx 错误，支付成功率下降至 87%，"
            "疑似上游支付通道接口异常。请尽快确认处理方案并回复处理结果。"
        ),
    },
    {
        "id": "mock-2",
        "subject": "【客户投诉】A 客户升级投诉，要求今天内答复",
        "from": "客服部 <cs@company.com>",
        "received_at": "2026-08-06 08:02",
        "body_preview": (
            "A 客户对上周交付延误强烈不满，已升级至其管理层，要求今天内给出答复和补偿方案。"
            "请您尽快确认并回复。"
        ),
    },
    {
        "id": "mock-3",
        "subject": "X 项目合同条款变更，请审批",
        "from": "法务部 <legal@company.com>",
        "received_at": "2026-08-05 17:30",
        "body_preview": (
            "X 项目甲方提出付款条款变更，涉及 200 万尾款支付节点调整，需要您审批后我方才能签署。"
            "附件为变更对照稿，请审阅。"
        ),
    },
    {
        "id": "mock-4",
        "subject": "Q3 预算执行情况汇报",
        "from": "张经理 <zhang@company.com>",
        "received_at": "2026-08-05 16:12",
        "body_preview": (
            "Q3 预算执行率已到 78%，市场部超支约 15 万，建议在月底前调整预算分配。"
            "附详细数据报表，请您知悉。"
        ),
    },
    {
        "id": "mock-5",
        "subject": "下周二产品评审会议邀请",
        "from": "产品部 <pm@company.com>",
        "received_at": "2026-08-05 15:40",
        "body_preview": (
            "下周二 10:00 举行产品 2.0 需求评审会，请您拨冗出席，会上将确认下季度开发优先级。"
        ),
    },
    {
        "id": "mock-6",
        "subject": "供应商报价询问：能否在 9 月前交付？",
        "from": "供应商 <vendor@partner.com>",
        "received_at": "2026-08-05 14:05",
        "body_preview": (
            "关于我们上月询价的 XX 设备，请问贵司能否在 9 月前完成交付？价格如有调整也请告知。"
        ),
    },
    {
        "id": "mock-7",
        "subject": "[Newsletter] AI 行业周报 第 88 期",
        "from": "科技周报 <newsletter@techweekly.com>",
        "received_at": "2026-08-05 12:00",
        "body_preview": "本期内容：大模型行业最新动态、企业数字化案例分享、本周活动预告。",
    },
    {
        "id": "mock-8",
        "subject": "系统通知：云服务器自动续费提醒",
        "from": "云平台 <noreply@cloudservice.com>",
        "received_at": "2026-08-05 10:30",
        "body_preview": "您的云服务器将于 8 月 20 日自动续费，金额 ¥1,299.00，如需变更请登录控制台。",
    },
]


class MailFetcher:
    """IMAP 邮件拉取器；未配置真实邮箱时自动使用 Mock 样例。"""

    def __init__(self) -> None:
        self._config = config

    @property
    def is_mock(self) -> bool:
        """当前是否为 Mock 模式（未配置真实 IMAP）。"""
        return not self._config.imap_configured

    def fetch_recent(self, limit: int | None = None, unread_only: bool = True) -> list[Email]:
        """拉取最近未读邮件，返回结构化 Email 列表；失败时返回空列表。"""
        limit = limit or self._config.EMAIL_FETCH_LIMIT
        if self.is_mock:
            logger.info("email.mail_fetcher", "IMAP 未配置，使用 Mock 样例邮件演示")
            return self._fetch_mock(limit)
        return self._fetch_imap(limit, unread_only)

    # ---------------- Mock 路径 ----------------
    def _fetch_mock(self, limit: int) -> list[Email]:
        items = [Email(**m) for m in _MOCK_EMAILS][:limit]
        logger.info("email.mail_fetcher", f"Mock 拉取 {len(items)} 封邮件")
        return items

    # ---------------- IMAP 路径 ----------------
    def _connect(self):
        """建立 IMAP 连接并登录，认证失败抛异常由上层处理。"""
        c = self._config
        conn = (
            imaplib.IMAP4_SSL(c.IMAP_SERVER, c.IMAP_PORT)
            if c.IMAP_USE_SSL
            else imaplib.IMAP4(c.IMAP_SERVER, c.IMAP_PORT)
        )
        conn.login(c.IMAP_EMAIL, c.IMAP_PASSWORD)
        return conn

    def _fetch_imap(self, limit: int, unread_only: bool) -> list[Email]:
        conn = None
        try:
            conn = self._connect()
            conn.select("INBOX")
            criteria = "UNSEEN" if unread_only else "ALL"
            _, data = conn.search(None, criteria)
            msg_ids = data[0].split()
            if not msg_ids:
                logger.info("email.mail_fetcher", "收件箱中没有符合条件的邮件")
                return []
            msg_ids = msg_ids[-limit:]  # 只取最近的 limit 封
            emails: list[Email] = []
            for num in msg_ids:
                _, msg_data = conn.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                message = email.message_from_bytes(raw)
                emails.append(self._to_struct(num, message))
            logger.info("email.mail_fetcher", f"IMAP 拉取 {len(emails)} 封未读邮件")
            return emails
        except imaplib.IMAP4.error as e:
            # 连接失败 / 认证失败
            logger.error("email.mail_fetcher", f"IMAP 连接或认证失败: {e}")
            return []
        except Exception as e:  # 其余异常不阻塞页面
            logger.error("email.mail_fetcher", f"拉取邮件失败: {e}")
            return []
        finally:
            try:
                if conn is not None:
                    conn.logout()
            except Exception:
                pass

    # ---------------- 解析辅助 ----------------
    @classmethod
    def _to_struct(cls, msg_id, message: email.message.Message) -> Email:
        """将 email.message.Message 转为 Email 对象（Pydantic alias 处理 "from" 字段）。"""
        # IMAP search 返回的编号是 bytes（如 b'2860'），需解码为字符串作唯一 id
        if isinstance(msg_id, bytes):
            msg_id = msg_id.decode("utf-8", errors="replace")
        return Email(
            id=str(msg_id),
            subject=cls._decode_mime(message.get("Subject", "")),
            from_=cls._decode_mime(message.get("From", "")),
            received_at=cls._decode_date(message.get("Date", "")),
            body_preview=cls._extract_preview(message, config.EMAIL_BODY_PREVIEW_LEN),
        )

    @staticmethod
    def _decode_mime(value: str) -> str:
        """解码 MIME 编码的文本（如 =?utf-8?B?...?=）。"""
        if not value:
            return ""
        try:
            parts = decode_header(value)
        except Exception:
            return str(value)
        out: list[str] = []
        for text, charset in parts:
            if isinstance(text, bytes):
                out.append(text.decode(charset or "utf-8", errors="replace"))
            else:
                out.append(str(text))
        return "".join(out)

    @staticmethod
    def _decode_date(raw: str) -> str:
        """把邮件 Date 头格式化为 YYYY-MM-DD HH:MM。"""
        if not raw:
            return ""
        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(raw).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw

    @classmethod
    def _extract_preview(cls, message: email.message.Message, limit: int) -> str:
        """提取正文纯文本并截断为预览。"""
        body = cls._get_plain_body(message)
        body = re.sub(r"\s+", " ", body).strip()
        return body[:limit]

    @staticmethod
    def _get_plain_body(message: email.message.Message) -> str:
        """递归提取纯文本正文；无纯文本时退化为去除标签的 HTML。"""
        def _decode(payload: bytes | None, charset: str | None) -> str:
            if not payload:
                return ""
            return payload.decode(charset or "utf-8", errors="replace")

        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    disposition = str(part.get("Content-Disposition") or "")
                    if "attachment" in disposition:
                        continue
                    return _decode(part.get_payload(decode=True), part.get_content_charset())
            # 无纯文本，退化为 HTML 去标签
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    html = _decode(part.get_payload(decode=True), part.get_content_charset())
                    return re.sub(r"<[^>]+>", " ", html)
            return ""
        return _decode(message.get_payload(decode=True), message.get_content_charset())


def fetch_emails(limit: int | None = None, unread_only: bool = True) -> list[Email]:
    """技能对外工具：拉取最近未读邮件。"""
    return MailFetcher().fetch_recent(limit=limit, unread_only=unread_only)


__all__ = ["MailFetcher", "fetch_emails"]
