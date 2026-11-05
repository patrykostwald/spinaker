"""Puls serwera dla paska centrum: token z env (stałoczasowe porównanie), tylko liczby, bez treści maili."""
from unittest.mock import patch

import pytest
from django.test import Client

from news.models import DutyAlarm
from news.poczta_models import MailMessage

pytestmark = pytest.mark.django_db
URL = '/api/puls/'


def test_bez_tokenu_na_serwerze_503():
    with patch.dict('os.environ', {'PULS_TOKEN': ''}):
        assert Client().get(URL, HTTP_X_PULS_TOKEN='x').status_code == 503


def test_zly_token_403():
    with patch.dict('os.environ', {'PULS_TOKEN': 'sekret'}):
        assert Client().get(URL, HTTP_X_PULS_TOKEN='inny').status_code == 403
        assert Client().get(URL).status_code == 403


def test_dobry_token_liczby_bez_tresci():
    MailMessage.objects.create(mailbox='kontakt', uid=1, subject='Tajny temat', body='treść', status='new')
    MailMessage.objects.create(mailbox='kontakt', uid=2, subject='Eskalacja', body='treść', status='escalated')
    DutyAlarm.objects.create(key='a', rule='budget', severity='warning', title='Budżet', instruction='sprawdź')
    with patch.dict('os.environ', {'PULS_TOKEN': 'sekret'}):
        r = Client().get(URL, HTTP_X_PULS_TOKEN='sekret')
    assert r.status_code == 200
    d = r.json()
    assert d['poczta']['nowe'] == 1 and d['poczta']['czekaja_decyzji'] == 1
    assert d['dyzurny'] == {'bledy': 1, 'nazwy': ['budget']}
    assert set(d) >= {'poczta', 'kopia_b2', 'x', 'diagnozy', 'dyzurny', 'czas'}
    tekst = r.content.decode()
    assert 'Tajny temat' not in tekst and 'treść' not in tekst
