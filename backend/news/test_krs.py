from datetime import date

import pytest

from news import krs, krs_agent
from news.political_models import PublicFigure, PublicFigureOrganisationRelation

ODPIS = {'odpis': {
    'naglowekP': {'wpis': [{'numerWpisu': 1, 'dataWpisu': '25.07.2001'}, {'numerWpisu': 6, 'dataWpisu': '04.09.2024'}]},
    'dane': {
        'dzial1': {'danePodmiotu': {'nazwa': [{'nazwa': 'FUNDACJA TESTOWA POMOCY', 'nrWpisuWprow': '1'}],
                                    'formaPrawna': [{'formaPrawna': 'FUNDACJA', 'nrWpisuWprow': '1'}]}},
        'dzial2': {
            'reprezentacja': [{'nazwaOrganu': [{'nazwaOrganu': 'ZARZĄD FUNDACJI', 'nrWpisuWprow': '1'}], 'sklad': [
                {'nazwisko': [{'nazwisko': {'nazwiskoICzlon': 'K*******'}, 'nrWpisuWprow': '1'}],
                 'imiona': [{'imiona': {'imie': 'J**'}, 'nrWpisuWprow': '1'}],
                 'funkcjaWOrganie': [{'funkcjaWOrganie': 'PREZES ZARZĄDU', 'nrWpisuWprow': '1'}]}]}],
            'organNadzoru': [{'sklad': [
                {'nazwisko': [{'nazwisko': {'nazwiskoICzlon': 'K*******'}, 'nrWpisuWprow': '1', 'nrWpisuWykr': '6'}],
                 'imiona': [{'imiona': {'imie': 'J**'}, 'nrWpisuWprow': '1', 'nrWpisuWykr': '6'}]}]}],
        },
    }}}


def test_parse_masks_and_organ_matching():
    extract = krs.parse('0000012345', 'S', ODPIS)
    assert extract.name == 'FUNDACJA TESTOWA POMOCY' and extract.kind == 'foundation' and extract.sector == 'ngo'
    people = krs.matching_persons(extract, 'Jan Kowalski')
    assert len(people) == 2  # ta sama maska w zarządzie i w organie nadzoru — sama maska nie wystarcza
    board = [p for p in people if krs.same_organ('prezes zarządu', p.organ, p.function)]
    assert len(board) == 1 and board[0].since == date(2001, 7, 25) and board[0].until is None
    oversight = [p for p in people if krs.same_organ('członek rady fundacji', p.organ, p.function)]
    assert len(oversight) == 1 and oversight[0].until == date(2024, 9, 4)
    assert not krs.matching_persons(extract, 'Jan Nowak') and not krs.mask_fits('K*******', 'Kowal') and krs.mask_fits('K*******', 'Kowalska')  # maska nie rozróżni — dlatego wymagamy źródła
    assert krs.names_match('Fundacja Testowa Pomocy', extract.name) and not krs.names_match('Fundacja Batorego', extract.name)
    assert krs.normalize_krs('12345') == '0000012345' and krs.normalize_krs('abc') == ''


@pytest.mark.django_db
def test_agent_confirms_only_with_register_match_or_two_sources(monkeypatch):
    figure = PublicFigure.objects.create(canonical_name='Jan Kowalski', role_category='parliamentary', role_title='Poseł',
                                         evidence_url='https://sejm.gov.pl/x', import_key='test:jk')
    extract = krs.parse('0000012345', 'S', ODPIS)
    monkeypatch.setattr(krs, 'fetch', lambda number: extract if number == '0000012345' else None)
    # Strony źródeł „pobieramy” — tylko inny.pl i example.org wymieniają osobę i podmiot.
    monkeypatch.setattr(krs_agent, 'page_mentions', lambda url, surname, entity: 'nic.pl' not in url)
    source = {'url': 'https://example.org/a', 'title': 'Artykuł'}
    candidate = {'name': 'Fundacja Testowa Pomocy', 'krs': '0000012345', 'role': 'prezes zarządu', 'period': '',
                 'current': True, 'sector': 'ngo', 'sources': [source]}
    relation = krs_agent.verify(figure, candidate)
    assert relation and relation.verification_status == 'confirmed' and relation.verification_method == 'krs_register'
    assert relation.since == date(2001, 7, 25) and relation.relation_status == 'current' and relation.organ == 'zarząd fundacji'
    assert relation.organisation.name == 'Fundacja Testowa Pomocy' and relation.organisation.official_register_url.startswith('https://')

    # Rola, której KRS nie pokazuje (np. komitet), jednym źródłem — nie zapisujemy.
    lonely = {**candidate, 'role': 'fundator'}
    assert krs_agent.verify(figure, lonely) is None
    # Dwa niezależne serwisy — zapisujemy jako „potwierdzone w źródłach”.
    two = {**lonely, 'sources': [source, {'url': 'https://inny.pl/b', 'title': 'Inny'}]}
    assert krs_agent.verify(figure, two).verification_method == 'public_sources'
    # Dwa źródła, ale jedno nie wymienia osoby — nie wystarcza.
    reasons = []
    fake = {**lonely, 'sources': [source, {'url': 'https://nic.pl/c', 'title': 'Nic'}]}
    assert krs_agent.verify(figure, fake, reasons) is None and 'sprawdzonych źródeł: 1' in reasons[0]
    # Zły numer KRS albo nazwa niezgodna z rejestrem — nic.
    assert krs_agent.verify(figure, {**candidate, 'krs': '0000099999'}) is None
    assert krs_agent.verify(figure, {**candidate, 'name': 'Zupełnie Inny Podmiot'}) is None
    assert PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed').count() == 2
