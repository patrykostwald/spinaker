import csv
import io
import json
import xml.etree.ElementTree as ET
from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from news.clinic_models import ClinicDailyMessage, SpinDiagnosis
from news.political_models import PoliticalAccount, PublicFigure
from news.test_clinic import account, post
from news.test_clinic_archives import fresh_throttle  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def _diagnosis(status='approved', headline='Teza „ąę”', **extra):
    owner = PoliticalAccount.objects.first() or account()
    return SpinDiagnosis.objects.create(post=post(owner, str(SpinDiagnosis.objects.count() + 500)), status=status, verdict='spin',
                                        intensity=70, headline=headline, summary='Krótko', diagnosed_at=timezone.now(), **extra)


def _rows(response):
    text = response.content.decode('utf-8')
    assert text.startswith('﻿')
    return list(csv.reader(io.StringIO(text.lstrip('﻿')), delimiter=';'))


def test_csv_export_is_utf8_with_bom_polish_headers_and_only_published(fresh_throttle):
    _diagnosis()
    _diagnosis(status='pending_review', headline='Szkic')
    response = APIClient().get('/api/export/diagnozy.csv')
    assert response.status_code == 200 and response['Content-Type'].startswith('text/csv')
    rows = _rows(response)
    assert rows[0][:3] == ['Numer diagnozy', 'Data wpisu', 'Obóz'] and len(rows) == 2
    assert 'Teza „ąę”' in rows[1] and all('Szkic' not in cell for row in rows for cell in row)
    assert 'Treść wpisu' not in rows[0] and not any('Deficyt' in cell for cell in rows[1])  # treści wpisów z X nie eksportujemy


def test_csv_export_respects_filters_and_neutralises_formulas(fresh_throttle):
    _diagnosis(headline='=HYPERLINK("http://zlo")')
    _diagnosis(headline='Inna')
    only = _rows(APIClient().get('/api/export/diagnozy.csv', {'q': 'Inna'}))
    assert len(only) == 2 and only[1][8] == 'Inna'
    formula = _rows(APIClient().get('/api/export/diagnozy.csv', {'q': 'HYPERLINK'}))
    assert formula[1][8].startswith("'=")
    assert APIClient().get('/api/export/diagnozy.csv', {'intensity_min': '90', 'intensity_max': '10'}).status_code == 400


def test_json_export_has_meta_and_licence_placeholder(fresh_throttle):
    PublicFigure.objects.create(canonical_name='Ewa Abacka', role_category='parliamentary', role_title='Posłanka', evidence_url='https://sejm.example')
    PublicFigure.objects.create(canonical_name='Archiwalna', role_category='parliamentary', role_title='Poseł', evidence_url='https://x.example', archived=True)
    body = json.loads(APIClient().get('/api/export/osoby.json').content)
    assert body['zbior'] == 'osoby' and body['liczba'] == 1 and body['dane'][0]['nazwa'] == 'Ewa Abacka'
    assert 'ustalimy przed wersją końcową' in body['licencja']
    assert set(body['dane'][0]) == set(body['kolumny'])


def test_unknown_dataset_and_extension_return_404_and_rate_limit_applies(fresh_throttle):
    client = APIClient()
    assert client.get('/api/export/hasla.csv').status_code == 404 and client.get('/api/export/osoby.xml').status_code == 404
    codes = [client.get('/api/export/wskazniki.csv').status_code for _ in range(31)]
    assert codes.count(200) == 28 and codes[-1] == 429  # limit 30/h liczy też dwa wcześniejsze 404


def test_rss_feeds_are_valid_xml_and_only_published(fresh_throttle):
    _diagnosis()
    _diagnosis(status='pending_review', headline='Szkic')
    ClinicDailyMessage.objects.create(day=date(2026, 9, 28), camp='government', status='approved', message='Przekaz rządu', reviewed_at=timezone.now())
    ClinicDailyMessage.objects.create(day=date(2026, 9, 28), camp='opposition', status='pending_review', message='Nieopublikowany')
    for name, needle in (('diagnozy', 'Teza'), ('przekazy', 'Przekaz rządu'), ('raporty', None)):
        response = APIClient().get(f'/api/feeds/{name}.xml')
        assert response.status_code == 200 and response['Content-Type'].startswith('application/rss+xml')
        root = ET.fromstring(response.content)
        text = response.content.decode('utf-8')
        assert root.tag == 'rss' and ('Analiza AI' in text or name == 'raporty')
        assert 'Szkic' not in text and 'Nieopublikowany' not in text
        if needle:
            assert needle in text and root.find('./channel/item/pubDate') is not None
    assert APIClient().get('/api/feeds/nic.xml').status_code == 404
