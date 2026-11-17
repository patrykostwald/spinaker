"""Versioned, deterministic data templates. Never imports AI or external clients."""
from collections import Counter
import hashlib
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from news import clinic
from news.report_models import REPORT_TYPES
from news.techniques import technique_groups

WARSAW = ZoneInfo('Europe/Warsaw')
METHOD = {
    'pl': ('Próba obejmuje wybrane, zatwierdzone diagnozy, a nie wszystkie wypowiedzi. '
           'Nie jest reprezentatywna dla osób ani obozów. Obóz ustalono w chwili zebrania wpisu. '
           'Wskaźnik ważony spinu = (spin + 0,5 × częściowy spin) / liczba diagnoz; '
           'nie jest to odsetek wpisów ze spinem. Siła jest oceną diagnostyczną w skali 0-100. '
           'Technikę liczymy raz na diagnozę. Brak danych nie oznacza braku zjawiska. '
           'Niedostępność wpisu nie dowodzi jego usunięcia przez autora. '
           'Liczby i wybór najsilniejszych diagnoz liczy kod; modele opisują tylko przekazane wyniki. '
           'Teksty źródłowe nie są częścią zestawienia. Recenzje AI nie gwarantują bezbłędności.'),
    'en': ('The sample covers selected approved diagnoses, not all statements. It is not representative '
           'of people or political camps. Camp is recorded at collection time. Weighted spin index = '
           '(spin + 0.5 × partial spin) / diagnoses; this is not the percentage of posts containing spin. '
           'Intensity is a diagnostic assessment from 0 to 100. Each technique is counted once per diagnosis. '
           'Missing data does not establish absence. Unavailability does not prove deletion by the author. '
           'Code computes the figures and ranks diagnoses; models only describe supplied results. '
           'Source texts are excluded. AI reviews cannot guarantee an error-free report.'),
}


def thresholds():
    return {key: max(1, int(getattr(settings, setting))) for key, setting in (
        ('weeks', 'REPORTS_MIN_WEEKS'), ('weekly_per_camp', 'REPORTS_MIN_WEEKLY_PER_CAMP'),
        ('statements', 'REPORTS_MIN_STATEMENTS'), ('votes', 'REPORTS_MIN_VOTES'),
        ('research', 'REPORTS_MIN_RESEARCH'), ('topic', 'REPORTS_MIN_TOPIC'))}


def period(as_of=None):
    today = as_of or timezone.now().astimezone(WARSAW).date()
    end = today - timedelta(days=today.weekday())  # exclusive Monday: no partial weeks
    return end - timedelta(weeks=thresholds()['weeks']), end


def _at(day):
    return datetime.combine(day, time.min, WARSAW)


def diagnosis_rows(start, end, figure_id=None):
    diagnoses = clinic.published_diagnoses().filter(post__published_at__gte=_at(start),
                                                    post__published_at__lt=_at(end)).order_by('post__published_at', 'pk')
    figures = clinic.figures_by_account(set(diagnoses.values_list('post__account_id', flat=True))) if figure_id else {}
    rows = []
    for row in diagnoses:
        if figure_id and getattr(figures.get(row.post.account_id), 'pk', None) != int(figure_id):
            continue
        if row.post.camp_at_collection not in clinic.CAMPS or not row.post.url:
            continue
        rows.append({'id': f'diagnosis:{row.pk}', 'kind': 'diagnosis',
                     'date': row.post.published_at.astimezone(WARSAW).date().isoformat(),
                     'camp': row.post.camp_at_collection, 'verdict': row.verdict, 'intensity': row.intensity,
                     'headline': row.headline,
                     'techniques': sorted(technique_groups(row.techniques)),
                     'url': row.post.url, 'analysis_url': f'https://spin.clinic/klinika/{row.pk}'})
    return rows


def profile_rows(figure_id, start, end):
    from news.models import Ballot
    from news.political_models import PublicFigure, PoliticalPost, PublicFigureArticleReference
    from news.clinic_models import ClinicInterview, SpinDiagnosis
    figure = PublicFigure.objects.select_related('parliamentary_roster_entry').filter(pk=figure_id).first()
    if not figure:
        return [], ['Nie wybrano osoby z potwierdzonym profilem.']
    roster = figure.parliamentary_roster_entry
    votes = []
    if roster and roster.source == 'sejm' and roster.term and roster.external_id.isdigit():
        for ballot in Ballot.objects.filter(mp_id=int(roster.external_id), voting__term=roster.term,
                voting__article__published_date__gte=_at(start), voting__article__published_date__lt=_at(end)).select_related('voting__article'):
            votes.append({'id': f'ballot:{ballot.pk}', 'kind': 'vote',
                          'date': ballot.voting.article.published_date.astimezone(WARSAW).date().isoformat(),
                          'vote': ballot.vote, 'url': ballot.voting.article.url})
    posts = PoliticalPost.objects.filter(available=False, unavailable_at__gte=_at(start), unavailable_at__lt=_at(end))
    figures = clinic.figures_by_account(set(posts.values_list('account_id', flat=True)))
    for post in posts:
        if getattr(figures.get(post.account_id), 'pk', None) == figure.pk:
            own = SpinDiagnosis.objects.filter(post=post, status='approved', hidden_at=None, withdrawn_at=None).first()
            votes.append({'id': f'unavailable:{post.pk}', 'kind': 'unavailable',
                          'date': post.unavailable_at.astimezone(WARSAW).date().isoformat(), 'url': post.url,
                          'verdict': own.verdict if own else '', 'intensity': own.intensity if own else None})
    links = PublicFigureArticleReference.objects.filter(public_figure=figure, reference_kind='interviewee',
        verification_status='confirmed', verified_at__isnull=False, verified_by__isnull=False).values_list('article__url', flat=True)
    for interview in ClinicInterview.objects.filter(url__in=links, status='approved', hidden_at=None, day__gte=start, day__lt=end):
        votes.append({'id': f'interview:{interview.pk}', 'kind': 'interview', 'date': str(interview.day),
                      'url': interview.url, 'headline': interview.headline})
    # No matching by names and no inferred stance/vote alignment from unrelated records.
    return votes, ['Brak zweryfikowanych powiązań wypowiedzi z konkretnymi głosowaniami i zmianami stanowiska.',
                   'Wywiady uwzględniono wyłącznie przy potwierdzonym powiązaniu materiału z osobą.']


def message_signature(message):
    payload = {key: getattr(message, key) for key in ('thesis', 'themes', 'points', 'tone', 'status')}
    payload.update(day=str(message.day), camp=message.camp)
    payload['posts'] = list(message.posts.order_by('pk').values('pk', 'text', 'available', 'camp_at_collection'))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def gate(kind, rows, start, end, scope=None):
    if kind not in dict(REPORT_TYPES):
        raise ValueError('Nieznany typ raportu.')
    limits, missing = thresholds(), []
    measurements = []

    def require(key, actual, required, label):
        measurements.append({'key': key, 'actual': actual, 'required': required, 'label': label})
        if actual < required:
            missing.append(f'{label}: {actual}/{required}.')

    # Deduplicate evidence before testing any threshold.
    rows = list({r['id']: r for r in rows if start.isoformat() <= r['date'] < end.isoformat()}.values())
    diagnoses = [r for r in rows if r['kind'] == 'diagnosis']
    if kind in ('weekly', 'weekly_en', 'research'):
        for w in range(limits['weeks']):
            day = start + timedelta(weeks=w)
            for camp in clinic.CAMPS:
                n = sum(r['camp'] == camp and day.isoformat() <= r['date'] < (day + timedelta(weeks=1)).isoformat()
                        for r in diagnoses)
                require(f'{day}:{camp}', n, limits['weekly_per_camp'], f'{day} - {clinic.CAMP_LABELS[camp]}')
        full = start.weekday() == end.weekday() == 0 and end <= period()[1]
        require('complete_weeks', (end - start).days // 7 if full else 0, limits['weeks'], 'Pełne tygodnie')
    if kind == 'research':
        require('diagnoses', len(diagnoses), limits['research'], 'Diagnozy')
    if kind == 'profile':
        require('statements', len(diagnoses), limits['statements'], 'Zdiagnozowane wypowiedzi osoby')
        require('votes', sum(r['kind'] == 'vote' for r in rows), limits['votes'], 'Głosowania osoby')
        if not (scope or {}).get('figure_id'):
            missing.append('Wybierz osobę.')
    if kind == 'topic':
        require('topic_records', sum(r['kind'] in ('bill', 'amendment', 'stance', 'lobbying') for r in rows), limits['topic'], 'Zweryfikowane rekordy tematu')
        require('legislation', sum(r['kind'] in ('bill', 'amendment') for r in rows), 1, 'Projekty lub poprawki')
        require('statements', sum(r['kind'] == 'stance' for r in rows), 1, 'Wypowiedzi związane z tematem')
        if not (scope or {}).get('topic'):
            missing.append('Wybierz temat.')
    return {'ready': not missing, 'missing': missing, 'measurements': measurements, 'thresholds': limits}


def aggregate(rows):
    result = {}
    for camp in clinic.CAMPS:
        selected = [r for r in rows if r['kind'] == 'diagnosis' and r['camp'] == camp]
        counts = Counter(r['verdict'] for r in selected)
        weighted = (counts['spin'] + .5 * counts['partial']) / len(selected) if selected else None
        result[camp] = {'count': len(selected), 'verdicts': dict(counts),
                        'weighted_spin': round(weighted, 4) if weighted is not None else None,
                        'weighted_spin_percent': round(100 * weighted, 1) if weighted is not None else None,
                        'average_intensity': round(sum(r['intensity'] for r in selected) / len(selected), 2) if selected else None,
                        'techniques': dict(Counter(t for r in selected for t in set(r['techniques'])))}
    return result


def build(kind, scope=None):
    scope = scope or {}
    scope = {key: value for key, value in scope.items() if key in (
        ('figure_id',) if kind == 'profile' else ('topic',) if kind == 'topic' else ())}
    start, end = period()
    if kind == 'profile':
        start = end - timedelta(days=180)
    rows = diagnosis_rows(start, end, scope.get('figure_id') if kind == 'profile' else None) if kind != 'topic' else []
    if kind == 'profile' and not scope.get('figure_id'):
        rows = []
    limitations = []
    if kind == 'profile':
        extra, limitations = profile_rows(scope.get('figure_id'), start, end)
        rows.extend(extra)
    if kind in ('topic', 'profile'):
        from news import report_observations
        observations = report_observations.rows(start, end, topic=scope.get('topic'), figure_id=scope.get('figure_id')) if (
            scope.get('topic') if kind == 'topic' else scope.get('figure_id')) else []
        rows.extend(observations)
        if kind == 'topic':
            limitations.append('Zakres obejmuje tylko zweryfikowane obserwacje przypisane do wybranego tematu, nie całość prac legislacyjnych.')
            if not any(r['kind'] == 'lobbying' for r in observations):
                limitations.append('Brak zweryfikowanych sygnałów lobbingu w próbie. Nie oznacza to braku lobbingu.')
    readiness = gate(kind, rows, start, end, scope)
    display_start = end - timedelta(days=7) if kind in ('weekly', 'weekly_en') else start
    displayed = [r for r in rows if r['date'] >= display_start.isoformat()]
    signatures = {}
    stats = aggregate(displayed)
    facts = {f'camp:{camp}': value for camp, value in stats.items()}
    for camp in clinic.CAMPS:
        best = sorted((r for r in displayed if r['kind'] == 'diagnosis' and r['camp'] == camp),
                      key=lambda r: (-r['intensity'], r['id']))[:3]
        facts[f'top:{camp}'] = best
    if kind in ('weekly', 'weekly_en', 'research'):
        from news.message_stats import calculate_stats, post_rows
        messages = clinic.published_messages().filter(day__gte=display_start, day__lt=end).prefetch_related('posts')
        # Full source text is used only locally to recalculate the existing tone statistics.
        for message in messages:
            posts = list(message.posts.all())
            if any(not p.available for p in posts):
                continue
            data = calculate_stats(post_rows(posts), message.points, message.tone)
            facts[f'message:{message.pk}'] = {'date': str(message.day), 'camp': message.camp,
                'thesis': message.thesis, 'themes': message.themes, 'tone': data['tone'],
                'posts': data['posts'], 'tone_classified': data['tone_classified']}
            signatures[str(message.pk)] = message_signature(message)
            displayed.extend({'id': f'message-source:{message.pk}:{p.pk}', 'kind': 'message_source',
                              'date': str(message.day), 'url': p.url} for p in posts)
    if kind == 'profile':
        from news.political_models import PublicFigure
        person = PublicFigure.objects.filter(pk=scope.get('figure_id')).values('id', 'canonical_name', 'evidence_url').first()
        facts['person'] = person or {}
        facts['profile'] = {'statements': sum(r['kind'] == 'diagnosis' for r in displayed),
                            'votes': dict(Counter(r['vote'] for r in displayed if r['kind'] == 'vote')),
                            'unavailable': [r for r in displayed if r['kind'] == 'unavailable'],
                            'interviews': [r for r in displayed if r['kind'] == 'interview']}
        comparison = report_observations.comparisons(observations)
        facts['profile_comparisons'] = comparison
        if any(r['kind'] == 'stance' for r in observations):
            limitations[0] = ('Zmiany klasyfikacji stanowiska i zgodność z głosem dotyczą wyłącznie jawnie powiązanych, '
                              'zweryfikowanych obserwacji. Nie dowodzą intencji ani sprzeczności we wszystkich wypowiedziach.')
    if kind == 'topic':
        facts['topic'] = {'topic': scope.get('topic', ''), 'counts': dict(Counter(r['kind'] for r in observations)),
                          'lobbying_confidence': dict(Counter(r['confidence'] for r in observations if r['kind'] == 'lobbying')),
                          'observations': observations}
    lang = 'en' if kind == 'weekly_en' else 'pl'
    return {'version': 1, 'kind': kind, 'language': lang, 'start': str(display_start), 'end_exclusive': str(end),
            'baseline_start': str(start), 'generated_at': timezone.now().isoformat(),
            'rows': displayed, 'baseline_diagnoses': [r for r in rows if r['kind'] == 'diagnosis'],
            'message_signatures': signatures, 'scope': scope,
            'facts': facts, 'aggregates': stats, 'gate': readiness,
            'limitations': limitations, 'method': METHOD[lang], 'thresholds': thresholds()}


def readiness(scope=None):
    return [{'kind': key, 'label': label, **build(key, scope)['gate']} for key, label in REPORT_TYPES]


def sources_current(snapshot):
    """Revoked, changed or newly unavailable diagnoses invalidate private exports too."""
    from news.clinic_models import SpinDiagnosis, ClinicDailyMessage, ClinicInterview
    from news.models import Ballot
    from news.political_models import PoliticalPost, PublicFigure
    figure = None
    if snapshot.get('kind') == 'profile':
        figure = PublicFigure.objects.select_related('parliamentary_roster_entry').filter(
            pk=snapshot.get('scope', {}).get('figure_id')).first()
        expected = snapshot['facts'].get('person', {})
        if not figure or expected != {'id': figure.pk, 'canonical_name': figure.canonical_name, 'evidence_url': figure.evidence_url}:
            return False
    rows = {row['id']: row for row in snapshot.get('rows', []) + snapshot.get('baseline_diagnoses', [])}
    for row in rows.values():
        if row['kind'] == 'diagnosis':
            obj = clinic.published_diagnoses().filter(pk=int(row['id'].split(':')[1])).first()
            if (not obj or obj.verdict != row['verdict'] or obj.intensity != row['intensity']
                    or obj.headline != row.get('headline', '') or obj.post.url != row['url']
                    or obj.post.camp_at_collection != row['camp']
                    or obj.post.published_at.astimezone(WARSAW).date().isoformat() != row['date']
                    or sorted(technique_groups(obj.techniques)) != row['techniques']):
                return False
            if figure and getattr(clinic.figures_by_account([obj.post.account_id]).get(obj.post.account_id), 'pk', None) != figure.pk:
                return False
        elif row['kind'] == 'message_source':
            pk = int(row['id'].split(':')[-1])
            if (not PoliticalPost.objects.filter(pk=pk, available=True).exists()
                    or SpinDiagnosis.objects.filter(post_id=pk).exclude(hidden_at=None, withdrawn_at=None).exists()):
                return False
        elif row['kind'] == 'vote':
            obj = Ballot.objects.select_related('voting__article').filter(pk=int(row['id'].split(':')[1])).first()
            if not obj or obj.vote != row['vote'] or obj.voting.article.url != row['url']:
                return False
            roster = figure.parliamentary_roster_entry if figure else None
            if not roster or roster.source != 'sejm' or str(obj.mp_id) != roster.external_id or obj.voting.term != roster.term:
                return False
        elif row['kind'] == 'interview':
            if not ClinicInterview.objects.filter(pk=int(row['id'].split(':')[1]), status='approved',
                                                  hidden_at=None, headline=row['headline'], url=row['url']).exists():
                return False
        elif row['kind'] == 'unavailable':
            if not PoliticalPost.objects.filter(pk=int(row['id'].split(':')[1]), available=False,
                                                unavailable_at__isnull=False).exists():
                return False
    for pk, signature in snapshot.get('message_signatures', {}).items():
        obj = ClinicDailyMessage.objects.filter(pk=pk).first()
        if not obj or message_signature(obj) != signature:
            return False
    from news.report_observations import current
    return current(snapshot)
