from email.message import EmailMessage

import pytest

from news.mailbox import _store
from news.models import Source, SourceContactCard, SourceContactReply


def make_source():
    return Source.objects.create(name='Publisher', url='https://publisher.example')


def header_message(*, message_id='<reply@example.org>', in_reply_to='', subject='Zgoda'):
    message = EmailMessage()
    message['Message-ID'] = message_id
    message['From'] = 'Redakcja <kontakt@example.org>'
    message['Subject'] = subject
    message['Date'] = 'Tue, 16 Sep 2026 12:00:00 +0200'
    if in_reply_to:
        message['In-Reply-To'] = in_reply_to
    message.set_content('Treść nie powinna być zapisana.')
    return message.as_bytes()


@pytest.mark.django_db
def test_mailbox_stores_headers_only_and_links_known_delivery_reference():
    source = make_source()
    card = SourceContactCard.objects.create(source=source, delivery_reference='<sent@example.org>')
    assert _store(header_message(in_reply_to='<sent@example.org>')) is True
    reply = SourceContactReply.objects.get()
    assert reply.contact_card == card
    assert reply.subject == 'Zgoda'
    assert not hasattr(reply, 'body')


@pytest.mark.django_db
def test_mailbox_is_idempotent():
    make_source()
    raw = header_message()
    assert _store(raw) is True
    assert _store(raw) is False
    assert SourceContactReply.objects.count() == 1
