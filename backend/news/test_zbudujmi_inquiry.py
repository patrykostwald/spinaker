from unittest import mock

import pytest
from django.core.cache import cache
from django.test import Client


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()


def post(data, origin='https://zbudujmi.com'):
    return Client().post('/api/zbudujmi/zapytanie/', data, content_type='application/json', HTTP_ORIGIN=origin)


def test_inquiry_sends_mail_and_allows_cors():
    with mock.patch('news.zbudujmi_inquiry.send_account_mail', return_value=True) as send:
        r = post({'what': 'Sklep', 'm': 'Sklep ze stroikami', 'n': 'Anna', 'e': 'anna@firma.pl'})
    assert r.status_code == 200 and r['Access-Control-Allow-Origin'] == 'https://zbudujmi.com'
    assert 'Sklep ze stroikami' in send.call_args[0][2]


def test_inquiry_validation_honeypot_and_limit():
    with mock.patch('news.zbudujmi_inquiry.send_account_mail', return_value=True) as send:
        assert post({'m': '', 'e': ''}).status_code == 400
        assert post({'m': 'x', 'e': 'y', 'website': 'spam'}).status_code == 200 and not send.called
        codes = [post({'m': 'x', 'e': 'y'}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_inquiry_foreign_origin_has_no_cors_header():
    with mock.patch('news.zbudujmi_inquiry.send_account_mail', return_value=True):
        r = post({'m': 'x', 'e': 'y'}, origin='https://evil.example')
    assert 'Access-Control-Allow-Origin' not in r


def note(data, origin='https://zbudujmi.com'):
    return Client().post('/api/zbudujmi/uwagi/', data, content_type='application/json', HTTP_ORIGIN=origin)


@pytest.mark.django_db
def test_client_note_is_saved_and_mailed():
    from news.feedback_models import ClientNote
    with mock.patch('news.zbudujmi_inquiry.send_account_mail', return_value=True) as send:
        r = note({'p': 'Neoglass', 'u': '/podglad/neoglass-x1/', 'x': 0.4, 'y': 1.7, 's': 'Oferta', 'm': 'Większe logo', 'n': 'Ola', 'v': '390x844'})
    assert r.status_code == 200 and r['Access-Control-Allow-Origin'] == 'https://zbudujmi.com'
    saved = ClientNote.objects.get()
    assert (saved.project, saved.anchor, saved.text, saved.y) == ('neoglass', 'Oferta', 'Większe logo', 1.0)
    assert 'Większe logo' in send.call_args[0][2]


@pytest.mark.django_db
def test_client_note_validation_and_honeypot():
    from news.feedback_models import ClientNote
    with mock.patch('news.zbudujmi_inquiry.send_account_mail', return_value=True):
        assert note({'p': 'x', 'm': ''}).status_code == 400
        assert note({'p': 'x', 'm': 'spam', 'website': 'bot'}).status_code == 200
    assert ClientNote.objects.count() == 0
