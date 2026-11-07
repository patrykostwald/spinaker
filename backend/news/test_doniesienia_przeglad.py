import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from news.political_models import PublicFigure, PublicFigureMediaMention, RegisteredOrganisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def mention():
    f = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł')
    o = RegisteredOrganisation.objects.create(name='Fundacja Akademia Przyszłości', krs_number='0000000111', kind='foundation', official_register_url='https://ekrs.ms.gov.pl/x')
    return PublicFigureMediaMention.objects.create(public_figure=f, organisation=o, source_url='https://portal.example/a', source_title='T', quote='Cytat z artykułu.')


def test_list_shows_pending_with_link_and_quote(mention, capsys):
    call_command('przeszlosc_doniesienia_przeglad')
    out = capsys.readouterr().out
    assert f'#{mention.pk}' in out and 'https://portal.example/a' in out and 'Cytat z artykułu.' in out and 'KRS 0000000111' in out


def test_reject_and_publish_use_a_staff_user(mention, capsys):
    other = PublicFigureMediaMention.objects.create(public_figure=mention.public_figure, organisation=mention.organisation, source_url='https://portal.example/b', source_title='T2')
    get_user_model().objects.create_superuser('szef', 's@example.com', 'x')
    call_command('przeszlosc_doniesienia_przeglad', '--odrzuc', str(other.pk), '--publikuj', str(mention.pk), '999')
    out = capsys.readouterr().out
    mention.refresh_from_db(); other.refresh_from_db()
    assert mention.status == 'published' and mention.reviewed_by.username == 'szef'
    assert other.status == 'rejected' and 'OPUBLIKOWANO' in out and 'ODRZUCONO' in out and '#999: nie ma takiej pozycji' in out


def test_without_staff_user_the_command_refuses(mention):
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command('przeszlosc_doniesienia_przeglad', '--publikuj', str(mention.pk))
