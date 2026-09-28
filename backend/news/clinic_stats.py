"""Publiczne agregaty Kliniki; próbą są wpisy, nie prawdomówność osób."""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from news import clinic
from news.clinic_models import SpinDiagnosis
from news.political_models import PoliticalPost
from news.techniques import CANONICAL_TECHNIQUES, technique_groups

MIN_SAMPLE = 10
CACHE_KEY = 'clinic-public-stats:v1'


def sample(count):
    return {'count': count, 'enough_data': count >= MIN_SAMPLE}


def bucket():
    return {'diagnosed': 0, 'spin': 0, 'partial': 0, 'no_spin': 0, 'unclear': 0,
            'intensity_sum': 0, 'intensity_histogram': [0] * 5}


def add(bucket, row):
    bucket['diagnosed'] += 1
    if row.verdict in clinic.VERDICT_LABELS:
        bucket[row.verdict] += 1
    bucket['intensity_sum'] += row.intensity
    bucket['intensity_histogram'][min(4, row.intensity // 20)] += 1


def finish(bucket):
    count = bucket['diagnosed']
    bucket['average_intensity'] = round(bucket.pop('intensity_sum') / count, 2) if count else None
    bucket['enough_data'] = count >= MIN_SAMPLE
    bucket['intensity_histogram'] = [
        {'min': index * 20, 'max': index * 20 + (20 if index == 4 else 19), **sample(n)}
        for index, n in enumerate(bucket['intensity_histogram'])]
    return bucket


def stats_data():
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    today = clinic.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = today - timedelta(days=29), today + timedelta(days=1)
    published = clinic.published_diagnoses()
    rows = list(published.filter(diagnosed_at__gte=start, diagnosed_at__lt=end))
    figures = clinic.figures_by_account({row.post.account_id for row in rows})
    camps = {camp: bucket() for camp in clinic.CAMPS}
    parties, accounts = {}, {}
    techniques = {name: {camp: 0 for camp in clinic.CAMPS} for name in CANONICAL_TECHNIQUES}
    for row in rows:
        camp = row.post.camp_at_collection
        camps.setdefault(camp, bucket())
        add(camps[camp], row)
        affiliation = clinic.party_affiliation(figures.get(row.post.account_id))
        party = affiliation['party']
        code = party['code'] if party else 'unknown'
        group = parties.setdefault(code, {**bucket(), 'party': party, 'camps': {}})
        add(group, row)
        group['camps'][camp] = group['camps'].get(camp, 0) + 1
        key = (row.post.account_id, camp)
        account = accounts.setdefault(key, {
            'account_id': row.post.account_id, 'name': clinic.author_data(row.post, figures.get(row.post.account_id))['name'],
            'handle': row.post.account.handle, 'party': party, 'camp': camp, 'diagnosed': 0})
        account['diagnosed'] += 1
        for name in technique_groups(row.techniques):
            techniques[name][camp] = techniques[name].get(camp, 0) + 1
    for group in parties.values():
        group['camp'] = next(iter(group['camps'])) if len(group['camps']) == 1 else 'mixed'
        finish(group)
    for account in accounts.values():
        account['enough_data'] = account['diagnosed'] >= MIN_SAMPLE

    daily = {(start + timedelta(days=offset)).date().isoformat(): {
        camp: {key: 0 for key in ('read', 'screened', 'diagnosed', 'spins')} for camp in clinic.CAMPS
    } for offset in range(30)}
    screened = SpinDiagnosis.objects.all()
    # created_at to jedyny zapisany czas utworzenia rekordu strażnika.
    for metric, queryset, field, camp_field in (
        ('read', PoliticalPost.objects.all(), 'fetched_at', 'camp_at_collection'),
        ('screened', screened, 'created_at', 'post__camp_at_collection'),
        ('diagnosed', published, 'diagnosed_at', 'post__camp_at_collection'),
        ('spins', published.filter(verdict__in=['spin', 'partial']), 'diagnosed_at', 'post__camp_at_collection'),
    ):
        values = (queryset.filter(**{f'{field}__gte': start, f'{field}__lt': end}).order_by()
                  .annotate(day=TruncDate(field, tzinfo=timezone.get_current_timezone()))
                  .values('day', camp_field).annotate(n=Count('pk')))
        for value in values:
            camp = value[camp_field]
            if camp in clinic.CAMPS:
                daily[value['day'].isoformat()][camp][metric] = value['n']
    totals = {key: ({**value, 'enough_data': value['total'] >= MIN_SAMPLE,
                     'today_enough_data': value['today'] >= MIN_SAMPLE} if 'total' in value else value)
              for key, value in clinic.clinic_stats().items()}
    totals['by_camp'] = {camp: {**values, 'enough_data': values['diagnosed'] >= MIN_SAMPLE}
                         for camp, values in totals['by_camp'].items()}
    funnel = {key: sample(totals[source]['total']) for key, source in (
        ('read', 'read'), ('screened', 'screened'), ('diagnosed', 'diagnosed'), ('spin', 'spins'))}
    # To stan kolejki, nie liczba wszystkich historycznych przejść przez ten etap.
    funnel['flagged_queued'] = sample(screened.filter(status__in=['flagged', 'queued']).count())
    result = {
        'totals': totals, 'funnel': funnel, 'min_sample': MIN_SAMPLE,
        'window': {'days': 30, 'date_from': start.date().isoformat(), 'date_to': today.date().isoformat(),
                   'timezone': str(timezone.get_current_timezone()), 'diagnoses_by': 'diagnosed_at',
                   'totals_scope': 'all_time', 'funnel_scope': 'all_time',
                   'funnel_flagged_queued_definition': 'current_flagged_or_queued_records',
                   'funnel_is_historical_cohort': False},
        'daily': [{'date': day, 'by_camp': {camp: {**metrics, 'enough_data': metrics['diagnosed'] >= MIN_SAMPLE}
                                           for camp, metrics in values.items()}} for day, values in daily.items()],
        'by_camp': {camp: finish(group) for camp, group in camps.items()},
        'by_party': dict(sorted(parties.items())),
        'techniques': {name: {camp: sample(count) for camp, count in counts.items()} for name, counts in techniques.items()},
        'accounts': sorted(accounts.values(), key=lambda item: (-item['diagnosed'], item['account_id'], item['camp']))[:50],
    }
    cache.set(CACHE_KEY, result, 600)
    return result
