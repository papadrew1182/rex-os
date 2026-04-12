"""Email transport abstraction.

Three implementations selected via REX_EMAIL_TRANSPORT env var:
  - "noop" (default): swallows everything, returns success
  - "log": writes the rendered email to the logger at INFO
  - "smtp": uses smtplib via REX_SMTP_HOST/PORT/USER/PASSWORD/FROM

The system MUST work fully in-app even when SMTP is absent. Email is purely
an enhancement: notifications still write to the in-app inbox regardless.
"""

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

log = logging.getLogger("rex.email")


@dataclass
class EmailMessage_:
    to: str
    subject: str
    body: str
    html: str | None = None


class EmailTransport:
    name: str = "base"
    def send(self, msg: EmailMessage_) -> bool:
        raise NotImplementedError


class NoopTransport(EmailTransport):
    name = "noop"
    def send(self, msg: EmailMessage_) -> bool:
        return True


class LogTransport(EmailTransport):
    name = "log"
    def send(self, msg: EmailMessage_) -> bool:
        log.info("email_sent transport=log to=%s subject=%r", msg.to, msg.subject)
        log.info("email_body\n%s", msg.body)
        return True


class SmtpTransport(EmailTransport):
    name = "smtp"
    def __init__(self):
        self.host = os.getenv("REX_SMTP_HOST", "localhost")
        self.port = int(os.getenv("REX_SMTP_PORT", "587"))
        self.user = os.getenv("REX_SMTP_USER")
        self.password = os.getenv("REX_SMTP_PASSWORD")
        self.from_addr = os.getenv("REX_SMTP_FROM", "rex@localhost")
        self.use_tls = os.getenv("REX_SMTP_TLS", "true").lower() in ("1", "true", "yes")

    def send(self, msg: EmailMessage_) -> bool:
        try:
            em = EmailMessage()
            em["Subject"] = msg.subject
            em["From"] = self.from_addr
            em["To"] = msg.to
            em.set_content(msg.body)
            if msg.html:
                em.add_alternative(msg.html, subtype="html")
            with smtplib.SMTP(self.host, self.port, timeout=10) as s:
                if self.use_tls:
                    s.starttls()
                if self.user and self.password:
                    s.login(self.user, self.password)
                s.send_message(em)
            log.info("email_sent transport=smtp to=%s subject=%r", msg.to, msg.subject)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("email_failed transport=smtp to=%s error=%r", msg.to, exc)
            return False


_transport: EmailTransport | None = None


def get_transport() -> EmailTransport:
    global _transport
    if _transport is not None:
        return _transport
    name = os.getenv("REX_EMAIL_TRANSPORT", "noop").strip().lower()
    if name == "smtp":
        _transport = SmtpTransport()
    elif name == "log":
        _transport = LogTransport()
    else:
        _transport = NoopTransport()
    return _transport


def send_email(to: str, subject: str, body: str, html: str | None = None) -> bool:
    return get_transport().send(EmailMessage_(to=to, subject=subject, body=body, html=html))
