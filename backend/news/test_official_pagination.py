"""Synthetic official API responses; these tests never call the live API."""
from unittest.mock import call, patch

import pytest

from news.models import Article, Ballot, OfficialRecord, OfficialRevision, ParliamentaryVoting
from scraper.official import import_voting_period, import_voting_search


def summaries(start, stop):
    return [{'term': 10, 'sitting': 1, 'votingNumber': number} for number in range(start, stop)]


def test_period_reads_more_than_one_hundred_and_keeps_filters():
    with patch('scraper.official.fetch_json', side_effect=[summaries(1, 101), summaries(101, 106), []]) as fetch, \
            patch('scraper.official.import_voting', return_value=True) as save:
        assert import_voting_period(10, '2023-11-13', '2026-09-09') == 105
    assert save.call_args_list == [call(10, 1, number) for number in range(1, 106)]
    assert fetch.call_args_list == [call('/sejm/term10/votings/search', offset=offset, limit=100,
        dateFrom='2023-11-13', dateTo='2026-09-09') for offset in (0, 100, 105)]


def test_title_search_does_not_assume_short_page_means_complete():
    # Also handles a provider capping responses at the original default of 50.
    with patch('scraper.official.fetch_json', side_effect=[summaries(1, 51), summaries(51, 101), summaries(101, 106), []]) as fetch, \
            patch('scraper.official.import_voting', return_value=True) as save:
        assert import_voting_search(10, 'krypto') == 105
    assert [item.kwargs for item in fetch.call_args_list] == [
        {'offset': offset, 'limit': 100, 'title': 'krypto'} for offset in (0, 50, 100, 105)]
    assert save.call_count == 105


def test_repeated_or_shifted_page_fails_without_reimporting_duplicate():
    with patch('scraper.official.fetch_json', side_effect=[summaries(1, 3), summaries(2, 4)]), \
            patch('scraper.official.import_voting', return_value=True) as save:
        with pytest.raises(ValueError, match='repeated'):
            import_voting_search(10, 'test')
    assert save.call_args_list == [call(10, 1, 1), call(10, 1, 2)]


@pytest.mark.parametrize('bad_page', [
    {'items': []}, [None], [{'term': 9, 'sitting': 1, 'votingNumber': 1}],
    [{'term': 10, 'sitting': 1}], [{'term': 10, 'sitting': 0, 'votingNumber': 1}],
    [{'term': 10, 'sitting': True, 'votingNumber': 1}], summaries(1, 2) * 2,
])
def test_invalid_page_cannot_be_reported_as_success(bad_page):
    with patch('scraper.official.fetch_json', return_value=bad_page), \
            patch('scraper.official.import_voting') as save:
        with pytest.raises(ValueError, match='incomplete'):
            import_voting_search(10, 'test')
    save.assert_not_called()


@pytest.mark.django_db
def test_interrupted_period_can_be_replayed_without_duplicate_records_or_ballots():
    fail = True

    def response(path, **params):
        if path.endswith('/search'):
            offset = params['offset']
            if offset == 0:
                return summaries(1, 4)
            if offset == 3:
                if fail:
                    raise TimeoutError('Synthetic interruption')
                return summaries(4, 6)
            return []
        number = int(path.rsplit('/', 1)[-1])
        return {'term': 10, 'sitting': 1, 'votingNumber': number,
            'title': f'Test-only voting {number}', 'description': 'Synthetic motion',
            'date': '2026-01-01T12:00:00', 'kind': 'ELECTRONIC',
            'yes': 1, 'no': 0, 'totalVoted': 1, 'notParticipating': 0,
            'votes': [{'MP': 1, 'firstName': 'Test', 'lastName': 'Fixture', 'vote': 'YES'}]}

    with patch('scraper.official.fetch_json', side_effect=response):
        with pytest.raises(TimeoutError):
            import_voting_period(10, '2026-01-01', '2026-01-02')
        assert Article.objects.count() == 3
        fail = False
        assert import_voting_period(10, '2026-01-01', '2026-01-02') == 2
        assert import_voting_period(10, '2026-01-01', '2026-01-02') == 0
    assert Article.objects.count() == OfficialRecord.objects.count() == ParliamentaryVoting.objects.count() == 5
    assert Ballot.objects.count() == 5
    assert OfficialRevision.objects.count() == 0
