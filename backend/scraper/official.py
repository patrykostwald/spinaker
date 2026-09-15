"""Official records: retain the original payload and replace a roll call atomically."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import json
from urllib.parse import urlencode
from django.db import transaction
from django.utils import timezone
from news.models import Article, ArticleCategory, Ballot, FetchAttempt, OfficialRecord, OfficialRevision, ParliamentaryVoting, SourceType
from news.models import SourceAccessInstruction
from scraper.access_gate import approved_instruction, AccessDenied
from scraper.utils import fetch_feed, get_or_create_source, upsert_article

API = 'https://api.sejm.gov.pl'
VOTE_CODES = {'YES', 'NO', 'ABSTAIN', 'NO_VOTE', 'ABSENT', 'VOTE_VALID', 'VOTE_INVALID', 'PRESENT'}


def fetch_json(path, *, return_receipt=False, **params):
    provider = 'eli' if path.startswith('/eli/') else 'sejm'
    source = official_source(provider)
    query = urlencode(params, doseq=True)
    request_url = API + path + (f'?{query}' if query else '')
    instruction = approved_instruction(source, SourceAccessInstruction.Channel.API, request_url)
    if instruction is None:
        raise AccessDenied('no_approved_instruction')
    response = fetch_feed(request_url, hostname_transport=True, audit_source=source,
        audit_instruction=instruction, requested_kind=FetchAttempt.RequestedKind.API_RECORD,
        return_receipt=return_receipt)
    if return_receipt:
        raw, receipt = response
        return json.loads(raw.decode('utf-8')), receipt
    return json.loads(response.decode('utf-8'))


def official_source(provider):
    return get_or_create_source(name='Sejm Rzeczypospolitej Polskiej' if provider == 'sejm' else 'ELI — Dziennik Ustaw i Monitor Polski',
        url=API + ('/sejm' if provider == 'sejm' else '/eli'), source_type=SourceType.INSTITUTION)


def save_record(provider, external_id, article, api_url, data, fetch_attempt=None):
    record = OfficialRecord.objects.select_for_update().filter(provider=provider, external_id=external_id).first()
    if record and record.raw_data != data:
        OfficialRevision.objects.create(record=record, raw_data=record.raw_data, fetched_at=record.fetched_at)
    OfficialRecord.objects.update_or_create(provider=provider, external_id=external_id, defaults={
        'article': article, 'api_url': api_url, 'raw_data': data, 'fetched_at': timezone.now(),
        'fetch_attempt': fetch_attempt})


@transaction.atomic
def save_voting(data, term, sitting, number, *, fetch_attempt=None):
    # A partial or malformed response must never destroy previously imported ballots.
    if (data['term'], data['sitting'], data['votingNumber']) != (term, sitting, number) or not data.get('title') or not (data.get('description') or data.get('topic')):
        raise ValueError('Voting identity or motion missing')
    motion = data.get('description') or data['topic']
    votes = data['votes']
    if not isinstance(votes, list) or not votes:
        raise ValueError('Missing roll call')
    ids = [v['MP'] for v in votes]
    if len(set(ids)) != len(ids) or any(v.get('vote') not in VOTE_CODES for v in votes):
        raise ValueError('Invalid roll call')
    if any(not v.get('firstName') or not v.get('lastName') for v in votes):
        raise ValueError('Missing member identity')
    if 'totalVoted' in data and 'notParticipating' in data and len(votes) != data['totalVoted'] + data['notParticipating']:
        raise ValueError('Incomplete roll call: count differs from official totals')
    dt = datetime.fromisoformat(data['date'])
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=ZoneInfo('Europe/Warsaw'))
    path = f'/sejm/term{term}/votings/{sitting}/{number}'
    article, created = upsert_article(source=official_source('sejm'), title=data['title'], url=API + path,
        published_date=dt, category=ArticleCategory.VOTING, description=motion, ingestion_method='sejm')
    # Official corrections are applied together with their complete new payload.
    Article.objects.filter(pk=article.pk).update(title=data['title'][:500], description=motion, published_date=dt, date_precision='time')
    save_record('sejm', f'vote/{term}/{sitting}/{number}', article, API + path, data, fetch_attempt)
    voting, _ = ParliamentaryVoting.objects.update_or_create(term=term, sitting=sitting, number=number, defaults={
        'article': article, 'motion': motion, 'kind': data['kind'],
        'counts': {key: data[key] for key in ('yes', 'no', 'abstain', 'notParticipating', 'present', 'totalVoted', 'majorityType', 'majorityVotes') if key in data},
        'options': data.get('votingOptions', [])})
    voting.ballots.all().delete()
    Ballot.objects.bulk_create([Ballot(voting=voting, mp_id=v['MP'],
        name=' '.join(str(v[k]) for k in ('firstName', 'secondName', 'lastName') if v.get(k)),
        club=v.get('club', ''), vote=v['vote'], list_votes=v.get('listVotes', {})) for v in votes])
    # Signals also invalidate queries after official corrections, not just inserts.
    article.refresh_from_db()
    article.save(update_fields=['updated_at'])
    return created


def import_voting(term, sitting, number, *, guard=None):
    if not official_access_allowed('sejm', f'/sejm/term{term}/votings/{sitting}/{number}'):
        return 0
    data, receipt = fetch_json(f'/sejm/term{term}/votings/{sitting}/{number}', return_receipt=True)
    if guard:
        guard()
    return save_voting(data, term, sitting, number, fetch_attempt=receipt)


def _import_voting_pages(term, guard=None, **filters):
    if not official_access_allowed('sejm', f'/sejm/term{term}/votings/search'):
        return 0
    # The search endpoint defaults to 50 results. An empty page is the only
    # completion signal: a server-side page cap may be smaller than our limit.
    count, offset, seen = 0, 0, set()
    while True:
        if guard:
            guard()
        rows = fetch_json(f'/sejm/term{term}/votings/search', offset=offset, limit=100, **filters)
        if not isinstance(rows, list):
            raise ValueError('Invalid voting search page; import incomplete')
        if not rows:
            return count
        identities = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Invalid voting search identity; import incomplete')
            identity = (row.get('term'), row.get('sitting'), row.get('votingNumber'))
            if any(type(value) is not int or value <= 0 for value in identity) or identity[0] != term:
                raise ValueError('Invalid voting search identity; import incomplete')
            if identity in seen:
                # A repeated/shifted page must not silently mark this period as
                # complete. Previously committed votes are safe to replay.
                raise ValueError('Voting pagination repeated a record; import incomplete')
            seen.add(identity)
            identities.append(identity)
        for identity in identities:
            if guard:
                guard()
            count += import_voting(*identity, guard=guard) if guard else import_voting(*identity)
        offset += len(rows)


def import_voting_search(term, title):
    return _import_voting_pages(term, title=title)


def import_voting_period(term, date_from, date_to, *, guard=None):
    return _import_voting_pages(term, guard=guard, dateFrom=date_from, dateTo=date_to)


@transaction.atomic
def save_document(data, provider, external_id, api_url, url, category, date_key):
    title = data['title']
    if not title:
        raise ValueError('Missing official title')
    day = datetime.strptime(data[date_key], '%Y-%m-%d').date() if data.get(date_key) else None
    dt = datetime.combine(day, time.min, ZoneInfo('Europe/Warsaw')) if day else None
    article, created = upsert_article(source=official_source(provider), title=title, url=url, published_date=dt,
        category=category, ingestion_method=provider, description=title)
    Article.objects.filter(pk=article.pk).update(title=title[:500], description=title, published_date=dt, date_precision='day')
    save_record(provider, external_id, article, api_url, data)
    article.refresh_from_db()
    article.save(update_fields=['updated_at'])
    return created


def import_eli_year(publisher, year):
    if publisher not in {'DU', 'MP'} or not 1918 <= year <= timezone.now().year:
        raise ValueError('Invalid ELI journal or year')
    if not official_access_allowed('eli', '/eli/acts/search'):
        return 0
    offset, count = 0, 0
    while True:
        payload = fetch_json('/eli/acts/search', publisher=publisher, year=year, offset=offset, limit=100)
        items = payload['items']
        for row in items:
            identity = f"{publisher}/{year}/{row['pos']}"
            count += save_document(row, 'eli', identity, API + '/eli/acts/' + identity,
                'https://eli.gov.pl/eli/' + identity + '/ogl', ArticleCategory.LEGISLATION, 'promulgation')
        offset += len(items)
        if offset >= payload['totalCount']:
            return count
        if not items:
            raise ValueError('Incomplete ELI pagination')


def import_print(term, number):
    if not str(number).replace('-', '').isdigit():
        raise ValueError('Invalid print number')
    if not official_access_allowed('sejm', f'/sejm/term{term}/prints/{number}'):
        return 0
    path = f'/sejm/term{term}/prints/{number}'
    data = fetch_json(path)
    if str(data['number']) != str(number) or data['term'] != term:
        raise ValueError('Print identity mismatch')
    return save_document(data, 'sejm', f'print/{term}/{number}', API + path, API + path,
        ArticleCategory.PARLIAMENTARY_PRINT, 'deliveryDate')


def import_prints(term):
    # This endpoint returns the full list and ignores limit/offset parameters.
    if not official_access_allowed('sejm', f'/sejm/term{term}/prints'):
        return 0
    count = 0
    for row in fetch_json(f'/sejm/term{term}/prints'):
        if row['term'] != term:
            raise ValueError('Print term mismatch')
        path = f"/sejm/term{term}/prints/{row['number']}"
        identity = f"print/{term}/{row['number']}"
        old = OfficialRecord.objects.filter(provider='sejm', external_id=identity).first()
        if old and old.raw_data.get('changeDate') == row.get('changeDate') and row.get('changeDate'):
            continue
        count += save_document(row, 'sejm', identity, API + path, API + path,
            ArticleCategory.PARLIAMENTARY_PRINT, 'deliveryDate')
    return count


def import_eli_changes(since):
    if not official_access_allowed('eli', '/eli/changes/acts'):
        return 0
    count, offset, seen = 0, 0, set()
    while True:
        payload = fetch_json('/eli/changes/acts', since=since, offset=offset)
        items = payload['items']
        for row in items:
            identity = f"{row['publisher']}/{row['year']}/{row['pos']}"
            if identity in seen:
                raise ValueError('ELI pagination repeated a record; import incomplete')
            seen.add(identity)
            if row['publisher'] not in {'DU', 'MP'}:
                continue
            count += save_document(row, 'eli', identity, API + '/eli/acts/' + identity,
                'https://eli.gov.pl/eli/' + identity + '/ogl', ArticleCategory.LEGISLATION, 'promulgation')
        offset += len(items)
        if offset >= payload.get('totalCount', offset):
            return count
        if not items:
            raise ValueError('Incomplete ELI changes pagination')


def official_access_allowed(provider, path):
    source = official_source(provider)
    return approved_instruction(source, SourceAccessInstruction.Channel.API, API + path) is not None
