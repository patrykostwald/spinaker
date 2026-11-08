from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from news import krs
from news.political_models import PublicFigure, PublicFigureMediaMention, RegisteredOrganisation

pytestmark = pytest.mark.django_db
HEADER = 'public_figure_name,krs_number,category,source_url,source_title,source_outlet,published_on,quote,match_basis,organisation_name,city\n'
ROW = 'Jan Testowy,0000494148,mention,https://oko.press/a,Tytuł,oko.press,2024-07-15,"Zdanie z artykułu.",identifier,{name},{city}\n'


def fake_extract(name='FUNDACJA PROFETO.PL - SERCAŃSKI SEKRETARIAT NA RZECZ NOWEJ EWANGELIZACJI', city='WARSZAWA'):
    return SimpleNamespace(krs='0000494148', register='S', name=name, legal_form='FUNDACJA', kind='foundation', owners=[], persons=[], nip='6551971642',
                           regon='', seat_city=city, seat_postal_code='', seat_voivodeship='', public_url='https://x', sector='ngo')


def run(tmp_path, monkeypatch, row, extract, apply=True, flag=True):
    PublicFigure.objects.create(canonical_name='Jan Testowy')
    path = tmp_path / 'a.csv'
    path.write_text(HEADER + row, encoding='utf-8')
    monkeypatch.setattr(krs, 'fetch_status', lambda number, full=True, timeout=30: (extract, 'ok' if extract else 'missing'))
    out = StringIO()
    args = [str(path)] + (['--apply'] if apply else []) + (['--dodaj-podmioty'] if flag else [])
    call_command('przeszlosc_doniesienia_import', *args, stdout=out)
    return out.getvalue()


def test_figure_by_name_and_organisation_added_from_official_extract(tmp_path, monkeypatch):
    out = run(tmp_path, monkeypatch, ROW.format(name='Fundacja Profeto.pl - Sercański Sekretariat na rzecz Nowej Ewangelizacji', city='Warszawa'), fake_extract())
    assert 'DODANO: 1' in out and RegisteredOrganisation.objects.get().krs_number == '0000494148'
    mention = PublicFigureMediaMention.objects.get()
    assert mention.status == 'pending_review' and mention.public_figure.canonical_name == 'Jan Testowy'


def test_dry_run_adds_nothing_and_wrong_city_or_name_is_rejected(tmp_path, monkeypatch):
    out = run(tmp_path, monkeypatch, ROW.format(name='Fundacja Profeto.pl - Sercański Sekretariat na rzecz Nowej Ewangelizacji', city='Warszawa'), fake_extract(), apply=False)
    assert 'Do dodania: 1' in out and 'nowy podmiot z KRS' in out and not RegisteredOrganisation.objects.exists()
    assert not PublicFigureMediaMention.objects.exists()


def test_rejects_mismatch_and_requires_the_flag(tmp_path, monkeypatch):
    assert 'miejscowość niezgodna' in run(tmp_path, monkeypatch, ROW.format(name='Fundacja Profeto.pl - Sercański Sekretariat na rzecz Nowej Ewangelizacji', city='Gdańsk'), fake_extract())
    assert not RegisteredOrganisation.objects.exists()


def test_without_flag_unknown_organisation_is_an_error(tmp_path, monkeypatch):
    out = run(tmp_path, monkeypatch, ROW.format(name='X', city='Warszawa'), fake_extract(), flag=False)
    assert 'nie ma podmiotu w bazie' in out and not RegisteredOrganisation.objects.exists()
