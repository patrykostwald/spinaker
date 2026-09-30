"""Hourly, deterministic council audit. No network/model calls."""
from collections import Counter
from datetime import timedelta
from uuid import uuid4

from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone

from news import clinic, clinic_council as council, council_registry as registry
from news.clinic_models import CouncilCall, CouncilSeat, SpinDiagnosis
from news.council_health import WARSAW, bench, bench_key, day_start, error_kind
from news.models import RepairAction, RepairerState
from news.repairer import Run, compare_delete


def pending(now):
    return SpinDiagnosis.objects.filter(status__in=['queued', 'flagged'],
        post__published_at__gte=now - timedelta(hours=clinic._env_int('CLINIC_FRESH_HOURS', 24)),
        hidden_at__isnull=True, post__available=True)


def health(now):
    start = day_start(now)
    observations = {}
    for call in CouncilCall.objects.filter(created_at__gte=start, created_at__lte=now).order_by('created_at', 'pk'):
        observations.setdefault((call.provider, call.model), []).append((call.outcome, call.seconds))
    # Older deployments only have member records inside completed/failed diagnoses.
    legacy, camps = {}, {}
    for usage, camp in SpinDiagnosis.objects.filter(diagnosed_at__gte=start, diagnosed_at__lte=now).order_by('diagnosed_at', 'pk').values_list('usage', 'post__camp_at_collection'):
        for member in (usage or {}).get('council', {}).get('members', []):
            key = (member.get('provider', ''), member.get('model', ''))
            observation = ('ok' if member.get('status') == 'odpowiedział' else error_kind(member.get('note') or 'other'), member.get('seconds'))
            legacy.setdefault(key, []).append(observation)
            camps.setdefault((key, camp), []).append(observation)
    for member, entries in legacy.items():
        observations.setdefault(member, entries)
    seats = {(s.provider, s.model): s for s in CouncilSeat.objects.all()}
    candidates = council._members('CLINIC_COUNCIL', council.DEFAULT_COUNCIL)
    for member in [*seats, *candidates]:
        observations.setdefault(member, [])
    result = []
    for member, entries in observations.items():
        counts = Counter(e[0] for e in entries)
        times = [e[1] for e in entries if isinstance(e[1], (float, int))]
        streak = 0
        for outcome, _ in reversed(entries):
            if outcome not in ('402', '429', 'timeout'):
                break
            streak += 1
        seat = seats.get(member)
        camp_stats = {}
        for camp in clinic.CAMPS:
            sample = camps.get((member, camp), [])
            measured = [e[1] for e in sample if isinstance(e[1], (int, float))]
            camp_stats[camp] = {'n': len(sample), 'response_rate': sum(e[0] == 'ok' for e in sample) / len(sample) if sample else None,
                'seconds': sum(measured) / len(measured) if measured else None,
                'errors': dict(Counter(e[0] for e in sample if e[0] != 'ok'))}
        result.append({**registry.metadata(member), 'attempts': len(entries), 'successes': counts['ok'], 'camps': camp_stats,
            'response_rate': round(counts['ok'] / len(entries), 3) if entries else None,
            'errors': dict(counts - Counter(ok=counts['ok'])), 'seconds': round(sum(times) / len(times), 2) if times else None,
            'streak': streak, 'benched': bool(cache.get(bench_key(member, now))),
            'seat': seat.status if seat else 'config', 'last_error': error_kind(seat.last_error) if seat else 'ok',
            'available': member in candidates and registry.available(member)})
    return result


def quality(rows):
    result = {}
    for camp in clinic.CAMPS:
        sample = [r for r in rows if r.post.camp_at_collection == camp]
        claims = [c for r in sample for c in (r.claims or []) if isinstance(c, dict)]
        n = len(sample)
        result[camp] = {'n': n, 'unclear': sum(r.verdict == 'unclear' for r in sample) / n if n else None,
            'spin_share': sum(r.verdict == 'spin' for r in sample) / n if n else None,
            'mean_intensity': round(sum(r.intensity for r in sample) / n, 2) if n else None,
            'agreement': dict(Counter((r.usage or {}).get('council', {}).get('agreement', 'unknown') for r in sample)),
            'claims_n': len(claims), 'unverified': sum(c.get('assessment') == 'unverified' for c in claims) / len(claims) if claims else None,
            'degraded': sum(bool((r.usage or {}).get('council', {}).get('diversity', {}).get('degraded')) for r in sample)}
    return result


def observe(now):
    start = day_start(now)
    today = SpinDiagnosis.objects.filter(created_at__gte=start, created_at__lte=now)
    done = SpinDiagnosis.objects.filter(diagnosed_at__gte=start, diagnosed_at__lte=now).exclude(verdict='').exclude(status='failed')
    daily = max(0, clinic._env_int('CLINIC_DAILY_LIMIT', 8))
    last = SpinDiagnosis.objects.exclude(verdict='').exclude(status='failed').aggregate(last=Max('diagnosed_at'))['last']
    throughput = {camp: {
        'flagged': today.filter(post__camp_at_collection=camp, status='flagged').count(),
        'queued': today.filter(post__camp_at_collection=camp, status='queued').count(),
        'diagnosed': done.filter(post__camp_at_collection=camp).count(),
        'published': done.filter(post__camp_at_collection=camp, status='approved', hidden_at__isnull=True, post__available=True).count(),
    } for camp in clinic.CAMPS}
    target = clinic.paced_target(now.astimezone(WARSAW), daily - (1 if daily > 1 else 0))
    regular_done = clinic.diagnoses_today() - bool(clinic.featured_today())
    metrics = quality(list(done.select_related('post')))
    a, b = (metrics[c] for c in clinic.CAMPS)
    gap = (abs(a['spin_share'] - b['spin_share']) >= .3 or abs(a['mean_intensity'] - b['mean_intensity']) >= 20) if a['n'] and b['n'] else False
    return {'throughput': throughput, 'target': target, 'regular_done': regular_done,
        'daily_limit': daily, 'pending': pending(now).count(), 'budget_usd': clinic.budget_left(),
        'last_diagnosis': last.isoformat() if last else None,
        'hours_since_diagnosis': round((now - last).total_seconds() / 3600, 2) if last else None,
        'members': health(now), 'quality': metrics,
        'asymmetry_warning': f"Duża różnica; mała próba: koalicja n={a['n']}, opozycja n={b['n']}. To sygnał do kontroli, nie dowód stronniczości." if gap and min(a['n'], b['n']) < 20 else '',
        'runs': (RepairerState.objects.filter(key='diagnosis-runs').values_list('data', flat=True).first() or {}).get('runs', [])}


def run(*, dry_run=False, now=None):
    now = now or timezone.now()
    if not 7 <= now.astimezone(WARSAW).hour <= 23:
        return {'status': 'night'}
    token = uuid4().hex
    if not dry_run and not cache.add('council-audit-lock', token, 240):
        return {'status': 'locked'}
    ctx = Run(now, dry_run)
    try:
        data = observe(now)
        ranking = {}
        for member in data['members']:
            key = (member['provider'], member['model'])
            ranking[':'.join(key)] = member['response_rate'] or 0
            if member['streak'] >= 3 and not member['benched']:
                ctx.apply('auditor:bench', ':'.join(key), lambda key=key: bench(key, now), 'fixed',
                          'Ławka do północy Europe/Warsaw po co najmniej 3 kolejnych błędach 402/429/timeout; jutro automatyczny powrót.')
        ranking_key = f'council:ranking:{day_start(now).date()}'
        changed = ranking != cache.get(ranking_key, {})
        if changed and not dry_run:
            cache.set(ranking_key, ranking, 86400)
        if ranking and changed:
            ctx.record('auditor:roles', str(day_start(now).date()), 'fixed',
                       'Zapasowi w rolach uporządkowani według odsetka sukcesów dziś; skład bez zmian.')
        if (data['pending'] and data['regular_done'] < data['target']
                and data['budget_usd'] >= clinic.BUDGET_RESERVE_USD
                and now.astimezone(WARSAW).hour < 23 and clinic.clinic_ai.enabled()
                and not cache.get('clinic-diagnose-lock')):
            recent = RepairAction.objects.filter(rule='auditor:diagnose', created_at__gt=now - timedelta(hours=1)).exists()
            if not recent and (dry_run or cache.add('auditor:extra-diagnosis', True, 3600)):
                ctx.record('auditor:diagnose', 'clinic_diagnose_task', 'retried',
                           'Zlecono dodatkowy przebieg; worker zachowuje blokadę, budżet i limit dzienny.')
                if not dry_run:
                    from config.celery import app
                    try:
                        app.send_task('news.tasks.clinic_diagnose_task', retry=False)
                    except Exception:
                        ctx.record('auditor:dispatch', 'clinic_diagnose_task', 'failed', 'Nie potwierdzono przyjęcia zadania przez broker; próba pozostaje zarezerwowana na godzinę.')
        from news.repairer import operational_notifications
        operational_notifications(ctx)
        if not dry_run:
            RepairerState.objects.update_or_create(key='council-audit', defaults={'data': {'at': now.isoformat()}})
        return {'status': 'ok', 'dry_run': dry_run, **data, 'actions': ctx.actions}
    finally:
        if not dry_run:
            compare_delete('council-audit-lock', token)


def panel_section(now):
    from news.admin_status import card, metric
    from news.inquisitor import findings, review_card
    from news.clinic_models import InquisitorReview
    data = observe(now)
    labels = {'flagged': 'Oznaczone dziś', 'queued': 'W kolejce (utworzone dziś)', 'diagnosed': 'Zdiagnozowane dziś',
        'published': 'Opublikowane z dzisiejszych diagnoz', 'n': 'Liczebność próby (n)', 'unclear': 'Niejasne (0–1)',
        'spin_share': 'Udział spinów (0–1)', 'mean_intensity': 'Średnia siła', 'claims_n': 'Liczba twierdzeń',
        'unverified': 'Niezweryfikowane (0–1)', 'degraded': 'Ograniczony skład', 'attempts': 'Próby dziś',
        'successes': 'Odpowiedzi dziś', 'response_rate': 'Odsetek odpowiedzi (0–1)', 'seconds': 'Średni czas (s)',
        'target': 'Cel tempa (zwykłe diagnozy)', 'regular_done': 'Wykonane zwykłe diagnozy', 'daily_limit': 'Limit dnia',
        'pending': 'Świeże wpisy oczekujące', 'budget_usd': 'Pozostały budżet (USD)', 'hours_since_diagnosis': 'Godziny od ostatniej diagnozy'}
    items = []
    for camp in clinic.CAMPS:
        q = data['quality'][camp]
        values = {**data['throughput'][camp], **{k: v for k, v in q.items() if k != 'agreement'}}
        items.append(card(clinic.CAMP_LABELS[camp], 'ok', 'Dzisiejsza próba; proporcje 0–1. Zgodność: ' + str(q['agreement']),
                          metrics=[metric(labels[k], v) for k, v in values.items()]))
    for m in data['members']:
        items.append(card(m['model'], 'warn' if m['benched'] or not m['available'] else 'ok',
            f"{m['provider']} · {m['seat']} · ławka: {m['benched']} · błędy: {m['errors']} · ostatni: {m['last_error']}",
            metrics=[metric(labels[k], m[k]) for k in ('attempts', 'successes', 'response_rate', 'seconds')],
            items=[card(clinic.CAMP_LABELS[c], 'ok', 'Z zapisanych ocen członka; błędy: ' + str(m['camps'][c]['errors']),
                metrics=[metric(labels[k], m['camps'][c][k]) for k in ('n', 'response_rate', 'seconds')]) for c in clinic.CAMPS]))
    items.extend(card('Przebieg diagnoz', 'warn' if r['status'] != 'ok' else 'ok',
                      r['status'] + ': ' + r['summary'], r['at']) for r in data['runs'])
    reviews = InquisitorReview.objects.select_related('diagnosis').all()
    items.append(card('Do decyzji właściciela', 'warn' if reviews.filter(verdict='error', decided_at__isnull=True).exists() else 'ok',
        items=[review_card(r) for r in reviews.filter(verdict='error', decided_at__isnull=True)]))
    items.append(card('Ostatnie kontrole', 'ok', items=[review_card(r) for r in reviews[:10]]))
    items.append(card('Zarzuty z 7 dni', 'ok', 'Liczba kontroli diagnoz, w których uczestniczył dany model. Zarzut nie dowodzi winy członka.',
        items=[card(f"{r['camp']} · {r['member']}", 'warn', str(r['issues']), metrics=[metric('n', r['n'])]) for r in findings(now - timedelta(days=7), now)]))
    return card('Audytor-inkwizytor', 'warn' if data['asymmetry_warning'] else 'ok',
        data['asymmetry_warning'] or 'Audyt bez AI; kontrole z równą miarą. Treść diagnoz pozostaje bez zmian.',
        metrics=[metric(labels[k], data[k]) for k in ('target', 'regular_done', 'daily_limit', 'pending', 'budget_usd', 'hours_since_diagnosis')], items=items)
