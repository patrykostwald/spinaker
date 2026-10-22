"""Account mail uses the project's existing SMTP configuration."""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from django.conf import settings

logger = logging.getLogger(__name__)


def send_account_mail(recipient, subject, body, headers=None):
    if not settings.SOURCE_MAIL_SMTP_ENABLED:
        return False
    message = EmailMessage()
    message['From'] = settings.SOURCE_MAIL_SMTP_FROM
    message['To'] = recipient
    message['Subject'] = subject
    for name, value in (headers or {}).items():  # np. List-Unsubscribe (wypisanie jednym kliknięciem, RFC 8058)
        message[name] = value
    message.set_content(body)
    try:
        with smtplib.SMTP_SSL(settings.SOURCE_MAIL_SMTP_HOST, settings.SOURCE_MAIL_SMTP_PORT,
                              timeout=15, context=ssl.create_default_context()) as client:
            client.login(settings.SOURCE_MAIL_SMTP_USERNAME, settings.SOURCE_MAIL_SMTP_PASSWORD)
            client.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.warning('Account mail delivery failed')
        return False
