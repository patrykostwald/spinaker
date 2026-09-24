"""Read-only IMAP intake for replies to source-access outreach."""
from __future__ import annotations

from datetime import timezone as datetime_timezone
from email import message_from_bytes
from email.header import decode_header
from email.utils import parsedate_to_datetime
from hashlib import sha256
import imaplib
import smtplib
import ssl
from email.message import EmailMessage

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from news.models import SourceContactCard, SourceContactReply


class SourceMailboxDisabled(RuntimeError):
    pass


def send_delivery_test(recipient: str) -> None:
    """Send one explicit control message; never used for source outreach."""
    required = ('SOURCE_MAIL_SMTP_HOST', 'SOURCE_MAIL_SMTP_USERNAME',
                'SOURCE_MAIL_SMTP_PASSWORD', 'SOURCE_MAIL_SMTP_FROM')
    if not settings.SOURCE_MAIL_SMTP_ENABLED or any(not getattr(settings, item) for item in required):
        raise SourceMailboxDisabled('missing_source_mail_smtp_configuration')
    message = EmailMessage()
    message['From'] = settings.SOURCE_MAIL_SMTP_FROM
    message['To'] = recipient
    message['Subject'] = 'spin.clinic — test dostarczalności poczty'
    message.set_content('To jest pojedynczy test dostarczalności skrzynki zrodla@spin.clinic.')
    with smtplib.SMTP_SSL(settings.SOURCE_MAIL_SMTP_HOST, settings.SOURCE_MAIL_SMTP_PORT,
                          context=ssl.create_default_context()) as client:
        client.login(settings.SOURCE_MAIL_SMTP_USERNAME, settings.SOURCE_MAIL_SMTP_PASSWORD)
        client.send_message(message)


def _header(message, name: str) -> str:
    values = []
    for value, encoding in decode_header(message.get(name, '')):
        if isinstance(value, bytes):
            values.append(value.decode(encoding or 'utf-8', errors='replace'))
        else:
            values.append(value)
    return ''.join(values).strip()


def _received_at(value: str):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed


def _store(raw: bytes) -> bool:
    message = message_from_bytes(raw)
    message_id = _header(message, 'Message-ID') or f'local-{sha256(raw).hexdigest()}'
    in_reply_to = _header(message, 'In-Reply-To')
    with transaction.atomic():
        if SourceContactReply.objects.filter(message_id=message_id).exists():
            return False
        card = SourceContactCard.objects.filter(delivery_reference=in_reply_to).first() if in_reply_to else None
        SourceContactReply.objects.create(
            contact_card=card,
            message_id=message_id,
            in_reply_to=in_reply_to,
            sender=_header(message, 'From')[:512],
            subject=_header(message, 'Subject')[:998],
            received_at=_received_at(_header(message, 'Date')),
        )
    return True


def sync_inbound(limit: int = 100) -> dict:
    """Import only envelope/header facts from newest IMAP messages.

    The function intentionally does not mark messages as read, store their
    bodies, send a reply, or alter access permission.
    """
    if not settings.SOURCE_MAIL_IMAP_ENABLED:
        raise SourceMailboxDisabled('SOURCE_MAIL_IMAP_ENABLED=false')
    required = ('SOURCE_MAIL_IMAP_HOST', 'SOURCE_MAIL_IMAP_USERNAME', 'SOURCE_MAIL_IMAP_PASSWORD')
    if any(not getattr(settings, item) for item in required):
        raise SourceMailboxDisabled('missing_source_mail_imap_configuration')
    client = imaplib.IMAP4_SSL(settings.SOURCE_MAIL_IMAP_HOST, settings.SOURCE_MAIL_IMAP_PORT)
    try:
        client.login(settings.SOURCE_MAIL_IMAP_USERNAME, settings.SOURCE_MAIL_IMAP_PASSWORD)
        status, _ = client.select('INBOX', readonly=True)
        if status != 'OK':
            raise RuntimeError('imap_inbox_unavailable')
        status, data = client.uid('search', None, 'ALL')
        if status != 'OK':
            raise RuntimeError('imap_search_failed')
        uids = data[0].split()[-limit:]
        created = duplicates = 0
        for uid in uids:
            status, result = client.uid('fetch', uid, '(BODY.PEEK[HEADER])')
            if status != 'OK' or not result or not isinstance(result[0], tuple):
                continue
            if _store(result[0][1]):
                created += 1
            else:
                duplicates += 1
        return {'scanned': len(uids), 'created': created, 'duplicates': duplicates}
    finally:
        try:
            client.logout()
        except imaplib.IMAP4.error:
            pass
