from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
import smtplib
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Dashboard, DashboardWidget, ReportSchedule


@dataclass
class EmailSendResult:
    ok: bool
    provider: str
    message_id: str | None = None
    error: str | None = None


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, recipients: list[str], subject: str, html_body: str, text_body: str | None = None) -> EmailSendResult:
        raise NotImplementedError


class LogEmailProvider(EmailProvider):
    def send(self, *, recipients: list[str], subject: str, html_body: str, text_body: str | None = None) -> EmailSendResult:
        payload = {
            "to": recipients,
            "subject": subject,
            "html_len": len(html_body),
            "text_len": len(text_body or ""),
        }
        print(f"[email-log] {payload}")
        return EmailSendResult(ok=True, provider="log", message_id=f"log-{int(datetime.utcnow().timestamp())}")


class SMTPEmailProvider(EmailProvider):
    def send(self, *, recipients: list[str], subject: str, html_body: str, text_body: str | None = None) -> EmailSendResult:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(text_body or "This report is best viewed as HTML.")
        message.add_alternative(html_body, subtype="html")

        try:
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                    self._auth_if_needed(smtp)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                    if settings.smtp_use_tls:
                        smtp.starttls()
                    self._auth_if_needed(smtp)
                    smtp.send_message(message)
        except Exception as exc:  # noqa: BLE001
            return EmailSendResult(ok=False, provider="smtp", error=str(exc))

        return EmailSendResult(ok=True, provider="smtp", message_id=message.get("Message-Id"))

    @staticmethod
    def _auth_if_needed(smtp: smtplib.SMTP) -> None:
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)


class EmailService:
    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def send_report_schedule(self, db: Session, *, schedule: ReportSchedule, delivered_at: datetime) -> EmailSendResult:
        recipients = [recipient for recipient in schedule.email_to if recipient]
        if not recipients:
            return EmailSendResult(ok=False, provider=self._provider_name, error="No recipients configured")

        subject, html_body, text_body = self._render_report_email(db, schedule=schedule, delivered_at=delivered_at)
        return self.provider.send(recipients=recipients, subject=subject, html_body=html_body, text_body=text_body)

    @property
    def _provider_name(self) -> str:
        return self.provider.__class__.__name__.replace("Provider", "").lower()

    @staticmethod
    def _render_report_email(db: Session, *, schedule: ReportSchedule, delivered_at: datetime) -> tuple[str, str, str]:
        dashboard = db.get(Dashboard, schedule.dashboard_id)
        dashboard_name = dashboard.name if dashboard else "Dashboard"

        widget_count = db.query(DashboardWidget).filter(DashboardWidget.dashboard_id == schedule.dashboard_id).count()
        date_label = delivered_at.strftime("%Y-%m-%d %H:%M UTC")
        dashboard_url = f"{settings.app_public_url.rstrip('/')}/dashboards/{schedule.dashboard_id}"

        subject = f"{schedule.name} - {dashboard_name}"
        text_body = (
            f"Report: {schedule.name}\n"
            f"Dashboard: {dashboard_name}\n"
            f"Delivered at: {date_label}\n"
            f"Widgets: {widget_count}\n"
            f"Open dashboard: {dashboard_url}\n"
        )
        html_body = (
            "<html><body>"
            f"<h2>{schedule.name}</h2>"
            f"<p><strong>Dashboard:</strong> {dashboard_name}</p>"
            f"<p><strong>Delivered at:</strong> {date_label}</p>"
            f"<p><strong>Widgets:</strong> {widget_count}</p>"
            f"<p><a href=\"{dashboard_url}\">Open dashboard</a></p>"
            "</body></html>"
        )
        return subject, html_body, text_body


def _build_provider() -> EmailProvider:
    if settings.email_provider.lower() == "smtp":
        return SMTPEmailProvider()
    return LogEmailProvider()


email_service = EmailService(_build_provider())
