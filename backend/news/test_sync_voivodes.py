from io import StringIO

import pytest
from django.core.management import call_command

from news.political_models import PublicFigure, PublicFigureRole, PublicOffice
from news.voivode_roster import VOIVODE_CONFIG, VoivodeRow, get_rows


def official_html(rows):
    return '<main>' + ''.join(
        f'<article><h2>{name} - wojewoda {region}</h2></article>' for name, region in rows
    ) + '</main>'


class Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_voivode_adapter_requires_each_of_the_16_official_regions():
    names = [
        'Anna Alfa', 'Beata Beta', 'Celina Gamma', 'Daniel Delta', 'Ewa Epsilon', 'Filip Zeta',
        'Grażyna Eta', 'Hubert Theta', 'Iwona Jota', 'Jan Kappa', 'Kamil Lambda', 'Lena Mu',
        'Marek Nu', 'Natalia Xi', 'Olga Omikron', 'Paweł Pi',
    ]
    rows = get_rows(http_get=lambda *args, **kwargs: Response(official_html(zip(names, VOIVODE_CONFIG))))
    assert len(rows) == 16
    assert {row.region for row in rows} == {item[0] for item in VOIVODE_CONFIG.values()}
    with pytest.raises(Exception, match='pełnych 16'):
        get_rows(http_get=lambda *args, **kwargs: Response(official_html([('Anna Testowa', 'dolnośląski')])))


@pytest.mark.django_db
def test_sync_voivodes_creates_durable_office_and_never_social_matching(monkeypatch):
    rows = [VoivodeRow('dolnoslaskie', 'Anna Żabska', 'Wojewoda Dolnośląski', 'Urząd testowy', 'https://gov.example/wojewodowie')]
    monkeypatch.setattr('news.management.commands.sync_voivodes.get_rows', lambda: rows)
    call_command('sync_voivodes', stdout=StringIO())
    figure = PublicFigure.objects.get(import_key='government:voivode:dolnoslaskie:holder:anna-zabska')
    office = PublicOffice.objects.get(import_key='public-office:voivode:dolnoslaskie')
    assert office.current_holder == figure
    assert PublicFigureRole.objects.get(public_office=office).public_figure == figure


@pytest.mark.django_db
def test_sync_voivodes_keeps_office_when_holder_changes(monkeypatch):
    monkeypatch.setattr('news.management.commands.sync_voivodes.get_rows', lambda: [
        VoivodeRow('dolnoslaskie', 'Pierwsza Osoba', 'Wojewoda Dolnośląski', 'Urząd testowy', 'https://gov.example/wojewodowie'),
    ])
    call_command('sync_voivodes', stdout=StringIO())
    first = PublicFigure.objects.get(import_key='government:voivode:dolnoslaskie:holder:pierwsza-osoba')
    office = PublicOffice.objects.get(import_key='public-office:voivode:dolnoslaskie')
    monkeypatch.setattr('news.management.commands.sync_voivodes.get_rows', lambda: [
        VoivodeRow('dolnoslaskie', 'Druga Osoba', 'Wojewoda Dolnośląski', 'Urząd testowy', 'https://gov.example/wojewodowie'),
    ])
    call_command('sync_voivodes', stdout=StringIO())
    office.refresh_from_db()
    assert office.current_holder.canonical_name == 'Druga Osoba'
    assert PublicFigureRole.objects.get(public_figure=first, public_office=office).status == 'former'
