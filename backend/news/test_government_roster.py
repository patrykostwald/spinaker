import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.government_roster import KPRM_CABINET_URL, cabinet_rows
from news.political_models import PoliticalAccountCandidate, PublicFigure

pytestmark = pytest.mark.django_db


class HtmlResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def official_cabinet_html(*, count=10):
    names = [
        'Adam Alfa', 'Beata Beta', 'Celina Gamma', 'Daniel Delta', 'Ewa Epsilon',
        'Filip Zeta', 'Grażyna Eta', 'Hubert Theta', 'Iwona Jota', 'Jan Kappa',
    ]
    members = ''.join(
        f'<article><p>{names[number]}</p><p>minister spraw testowych {number}</p></article>'
        for number in range(count)
    )
    return f'<main><h1>Członkowie Rady Ministrów</h1>{members}</main>'


def test_cabinet_adapter_reads_only_current_cabinet_pairs():
    rows = cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(official_cabinet_html()))
    assert len(rows) == 10
    assert rows[0].canonical_name == 'Adam Alfa'
    assert rows[0].role_title == 'minister spraw testowych 0'
    assert rows[0].source_url == KPRM_CABINET_URL
    assert rows[0].import_key == 'kprm-cabinet:adam-alfa'


def test_cabinet_adapter_fails_closed_for_missing_title_ambiguous_name_or_small_list():
    with pytest.raises(CommandError, match='nie potwierdza tytułu'):
        cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse('<main>brak</main>'))
    bad = '<h1>Członkowie Rady Ministrów</h1><p>nie wiadomo</p><p>minister testów</p>'
    with pytest.raises(CommandError, match='niejednoznaczne'):
        cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(bad))
    with pytest.raises(CommandError, match='tylko 1'):
        cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(official_cabinet_html(count=1)))


def test_command_dry_run_does_not_write_or_create_x_leads(monkeypatch, capsys):
    candidates = PoliticalAccountCandidate.objects.count()
    monkeypatch.setattr('news.management.commands.sync_public_figures.cabinet_rows',
        lambda: cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(official_cabinet_html())))
    call_command('sync_public_figures', source='cabinet', dry_run=True)
    assert not PublicFigure.objects.exists()
    assert PoliticalAccountCandidate.objects.count() == candidates
    assert 'Bez zapisu' in capsys.readouterr().out


def test_command_upserts_and_archives_only_previous_import(monkeypatch):
    monkeypatch.setattr('news.management.commands.sync_public_figures.cabinet_rows',
        lambda: cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(official_cabinet_html())))
    call_command('sync_public_figures', source='cabinet')
    entry = PublicFigure.objects.get(import_key='kprm-cabinet:adam-alfa')
    manual = PublicFigure.objects.create(canonical_name='Ręczna Osoba', role_category='political', role_title='Rola',
        evidence_url='https://example.test/evidence')
    monkeypatch.setattr('news.management.commands.sync_public_figures.cabinet_rows',
        lambda: cabinet_rows(http_get=lambda url, **kwargs: HtmlResponse(official_cabinet_html(count=10).replace(
            'Adam Alfa</p><p>minister spraw testowych 0', 'Nowa Osoba</p><p>minister spraw testowych 0'))))
    call_command('sync_public_figures', source='cabinet')
    entry.refresh_from_db(); manual.refresh_from_db()
    assert entry.archived and entry.status == 'former'
    assert not manual.archived
