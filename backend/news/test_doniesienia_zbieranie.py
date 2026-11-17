import pytest
from django.utils import timezone

from news import doniesienia_zbieranie as dz
from news.models import Article, Source
from news.political_models import PublicFigure, PublicFigureMediaMention, RegisteredOrganisation

pytestmark = pytest.mark.django_db


def fig(name='Jan Kowalski', **kw):
    return PublicFigure.objects.create(canonical_name=name, role_category='parliamentary', role_title='Poseł', **kw)


def org(name, krs, kind='foundation'):
    return RegisteredOrganisation.objects.create(name=name, krs_number=krs, kind=kind, official_register_url='https://ekrs.ms.gov.pl/x')


def art(title, desc='', n=[0]):
    n[0] += 1
    return Article.objects.create(source=Source.objects.get_or_create(name='Portal', defaults={'url': 'https://portal.example'})[0], title=title,
                                  description=desc, url=f'https://portal.example/{n[0]}', published_date=timezone.now())


def test_distinct_part_rejects_generic_and_short_names():
    assert dz.distinct_part('Fundacja Pomocy Dzieciom') is None
    assert dz.distinct_part('Fundacja Polska') is None
    assert dz.distinct_part('Fundacja Kasa') is None
    assert dz.distinct_part('Fundacja Wspierania Inicjatyw Lokalnych Orion') is not None
    assert dz.distinct_part('Stowarzyszenie Akademia Przyszłości') is not None


def test_candidate_when_full_person_name_and_full_org_name_share_an_article():
    f, o = fig(), org('Fundacja Akademia Przyszłości', '0000000111')
    art('Jan Kowalski i Fundacja Akademia Przyszłości: powiązania z ministerstwem', 'Opis.')
    art('Fundacja Akademia Przyszłości organizuje piknik')                                   # bez osoby: nie
    art('Kowalski pojawił się na pikniku', 'Fundacja Akademia Przyszłości')                  # samo nazwisko: nie
    pattern, index = dz.org_index()
    found = dz.candidates_for(f, pattern, index)
    assert len(found) == 1 and found[0]['org_id'] == o.pk and found[0]['category'] == 'alleged'
    assert 'fundacja akademia przyszłości' in found[0]['quote']


def test_homonym_and_generic_orgs_are_skipped_and_known_orgs_excluded_by_default():
    f = fig()
    fig('Jan Kowalski', import_key='dup')                                                    # imiennik: wstrzymane
    org('Fundacja Akademia Przyszłości', '0000000111')
    art('Jan Kowalski i Fundacja Akademia Przyszłości')
    pattern, index = dz.org_index()
    assert dz.candidates_for(f, pattern, index) == []


def test_collect_dry_run_then_apply_goes_to_review_queue_without_duplicates():
    f = fig()
    org('Fundacja Akademia Przyszłości', '0000000111')
    art('Jan Kowalski i Fundacja Akademia Przyszłości')
    assert dz.collect()['candidates'] == 1 and PublicFigureMediaMention.objects.count() == 0
    assert dz.collect(apply=True)['added'] == 1
    m = PublicFigureMediaMention.objects.get()
    assert m.status == 'pending_review' and m.match_basis == 'name_only' and m.collected_by == 'agent' and m.public_figure_id == f.pk
    assert dz.collect(apply=True)['skipped_existing'] == 1 and PublicFigureMediaMention.objects.count() == 1


def test_far_apart_names_and_guest_lists_are_not_candidates():
    f = fig()
    org('Fundacja Akademia Przyszłości', '0000000111')
    org('Fundacja Zielone Pola Mazowsza', '0000000112')
    org('Stowarzyszenie Rzeka Nadziei Polskiej', '0000000113')
    org('Fundacja Błękitny Horyzont Północy', '0000000114')
    filler = ' tekst zapełniający opis wydarzenia i zaproszeni goście ' * 4
    art('Opis', 'Jan Kowalski wystąpił na konferencji.' + filler + 'Partnerem była Fundacja Akademia Przyszłości.')          # daleko
    art('Lista', 'Goście: Jan Kowalski, Fundacja Akademia Przyszłości, Fundacja Zielone Pola Mazowsza, Stowarzyszenie Rzeka Nadziei Polskiej, Fundacja Błękitny Horyzont Północy')   # lista
    pattern, index = dz.org_index()
    assert dz.candidates_for(f, pattern, index) == []


def test_category_needs_strong_cue_near_the_organisation_not_anywhere_in_text():
    f = fig()
    org('Fundacja Akademia Przyszłości', '0000000111')
    art('Jan Kowalski o planach', 'Założyliśmy cel, mówi Jan Kowalski o Fundacja Akademia Przyszłości. ' + 'Inne zdanie. ' * 30 + 'Powiązane z tym sprawy.')
    pattern, index = dz.org_index()
    found = dz.candidates_for(f, pattern, index)
    assert len(found) == 1 and found[0]['category'] == 'mention'
    art('Fundator', 'Jan Kowalski jest fundatorem Fundacja Akademia Przyszłości.')
    assert 'alleged' in {c['category'] for c in dz.candidates_for(f, pattern, index)}


def test_clear_agent_queue_removes_only_unpublished_agent_rows():
    f, o = fig(), org('Fundacja Akademia Przyszłości', '0000000111')
    base = dict(public_figure=f, organisation=o, source_title='T')
    PublicFigureMediaMention.objects.create(source_url='https://x.example/1', collected_by='agent', **base)
    PublicFigureMediaMention.objects.create(source_url='https://x.example/2', collected_by='import', **base)
    PublicFigureMediaMention.objects.create(source_url='https://x.example/3', collected_by='agent', status='published', **base)
    assert dz.clear_agent_queue() == 1 and PublicFigureMediaMention.objects.count() == 2


def test_single_word_political_and_party_cases_are_not_candidates():
    f = fig()
    org('Skrzydła', '0000000201')                                  # jedno zwykłe słowo
    org('Komitet Obrony Demokracji', '0000000202')                  # polityczny
    org('Fundacja Akademia Przyszłości', '0000000111')
    party = PublicFigure.objects.create(canonical_name='Platforma Obywatelska', role_category='party', role_title='Partia', import_key='p')
    art('Jan Kowalski pod skrzydła premiera, Komitet Obrony Demokracji protestuje')
    art('Platforma Obywatelska i Fundacja Akademia Przyszłości')
    pattern, index = dz.org_index()
    assert dz.candidates_for(f, pattern, index) == [] and dz.candidates_for(party, pattern, index) == []


def test_list_layout_is_skipped_because_the_org_belongs_to_the_next_person():
    f = fig()
    org('Fundacja Dajemy Dzieciom Siłę', '0000000301')
    art('Konferencja', '- Jan Kowalski - rzecznik praw dziecka - Anna Nowak - Fundacja Dajemy Dzieciom Siłę - Piotr Wiśniewski - dyrektor')
    art('Goście', '▪ Jan Kowalski ▪ Fundacja Dajemy Dzieciom Siłę')
    pattern, index = dz.org_index()
    assert dz.candidates_for(f, pattern, index) == []
