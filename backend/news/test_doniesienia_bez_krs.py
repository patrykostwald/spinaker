from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from news.political_models import PublicFigure, PublicFigureMediaMention
from news.przeszlosc_doniesienia import mentions_for

pytestmark = pytest.mark.django_db
HEADER = 'public_figure_name,krs_number,category,source_url,source_title,source_outlet,published_on,quote,match_basis,organisation_name,entity_identifier,entity_register_url\n'
ROW = 'Jan Testowy,,mention,https://oko.press/a,Tytuł,oko.press,2024-07-15,"Zdanie.",name_only,{name},NIP 5861994708,{url}\n'


def load(tmp_path, row, apply=True):
    PublicFigure.objects.get_or_create(canonical_name='Jan Testowy')
    path = tmp_path / 'b.csv'
    path.write_text(HEADER + row, encoding='utf-8')
    out = StringIO()
    call_command('przeszlosc_doniesienia_import', str(path), *(['--apply'] if apply else []), stdout=out)
    return out.getvalue()


def test_entity_without_krs_goes_to_review_queue_then_appears_in_payload_after_publish(tmp_path, django_user_model):
    out = load(tmp_path, ROW.format(name='Jan Kowalski Usługi', url='https://prod.ceidg.gov.pl/CEIDG/CEIDG.Public.UI/Search.aspx'))
    assert 'DODANO: 1' in out
    m = PublicFigureMediaMention.objects.get()
    assert m.organisation is None and m.status == 'pending_review' and m.display_name == 'Jan Kowalski Usługi'
    assert mentions_for(m.public_figure)['count'] == 0                       # nic publicznego przed zatwierdzeniem
    staff = django_user_model.objects.create_user('r', password='x', is_staff=True)
    m.publish(staff)
    r = mentions_for(m.public_figure)['results'][0]['organisation']
    assert r['no_krs'] is True and r['name'] == 'Jan Kowalski Usługi' and r['identifier'] == 'NIP 5861994708' and r['register_url'].startswith('https://prod.ceidg')
    assert r['krs_number'] == '' and r['url'] == '' and r['extra_url'] == ''


def test_entity_row_needs_name_and_https_register_and_duplicates_are_skipped(tmp_path):
    assert 'wymaga organisation_name i entity_register_url' in load(tmp_path, ROW.format(name='X', url='http://nie-https.pl'))
    assert not PublicFigureMediaMention.objects.exists()
    good = ROW.format(name='X', url='https://prod.ceidg.gov.pl/')
    assert 'DODANO: 1' in load(tmp_path, good) and 'pominięto (już są): 1' in load(tmp_path, good)
    assert PublicFigureMediaMention.objects.count() == 1
