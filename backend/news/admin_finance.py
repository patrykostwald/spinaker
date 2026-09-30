"""Read recorded usage only. No inference from configured models or API limits."""
import math
import os
import threading
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.core.cache import cache
from django.db.models import Q, OuterRef, Subquery
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from news.clinic_models import ClinicInterview, SpinDiagnosis
from news.models import AIResearchCall
from news.political_models import PoliticalRead
from news.wallet_models import WalletBalance, PROVIDERS

WARSAW = ZoneInfo('Europe/Warsaw')
UNKNOWN = 'unknown'
AI_PROVIDERS = [('anthropic', 'Claude'), ('gemini', 'Gemini'), ('groq', 'Groq'),
                ('nim', 'NVIDIA'), ('openrouter', 'OpenRouter'), ('hf', 'Hugging Face'),
                ('cloudflare', 'Cloudflare'), ('mistral', 'Mistral'), ('pllum', 'PLLuM'),
                ('openai', 'OpenAI / AIResearchCall'), ('unknown', 'Nieustalony dostawca')]


class HistoryLimit(Exception):
    pass


def bounded_rows(query):
    # A very old balance must not load unlimited JSON on the request path.
    rows = list(query.order_by()[:5001])
    if len(rows) > 5000:
        raise HistoryLimit
    return rows


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def usage_event(stamp, usage, fallback_model=''):
    from news.clinic_ai import cost_usd
    usage = usage if isinstance(usage, dict) else {}
    model = str(usage.get('model') or fallback_model).lower()
    # Council overwrites the billing model with a roster. Do not price that
    # roster as Opus (the fallback in cost_usd) or as whichever name comes first.
    if model.startswith('konsylium:') or usage.get('council'):
        council = usage.get('council') or {}
        if council.get('escalated') is False:
            # This branch always uses _call_gemini; clinic_ai prices all Gemini
            # models with the same family tariff. The overwritten Claude model
            # in the escalated branch cannot be recovered in this way.
            return usage_event(stamp, {k: v for k, v in {**usage, 'model': 'gemini'}.items() if k != 'council'})
        return (stamp, 'anthropic' if council.get('escalated') else 'unknown', None, None)
    provider = ('gemini' if 'gemini' in model else 'anthropic'
                if any(family in model for family in ('claude', 'haiku', 'sonnet', 'opus')) else 'unknown')
    known = (provider != 'unknown' and all(number(usage.get(k)) is not None for k in ('input_tokens', 'output_tokens'))
             and ('web_search_requests' not in usage or number(usage['web_search_requests']) is not None))
    cost = cost_usd({**usage, 'model': model}) if known else None
    # A usage record may aggregate transcript chunks; not necessarily one call.
    return (stamp, provider, cost, 1 if usage and provider != 'unknown' else None)


def recorded_events(start, now):
    """Events carry (time, provider, cost or None, known call count or None)."""
    events = []
    for row in bounded_rows(SpinDiagnosis.objects.filter(diagnosed_at__gte=start, diagnosed_at__lte=now).values('diagnosed_at', 'usage', 'model_name')):
        events.append(usage_event(row['diagnosed_at'], row['usage'], row['model_name']))
    for row in bounded_rows(ClinicInterview.objects.filter(created_at__lte=now).filter(
            # Transcription failures retain usage without diagnosed_at.
            Q(diagnosed_at__gte=start) | Q(diagnosed_at__isnull=True, created_at__gte=start)
    ).values('created_at', 'diagnosed_at', 'usage', 'model_name')):
        stamp = row['diagnosed_at'] or row['created_at']
        if stamp > now:
            continue
        usage = row['usage'] if isinstance(row['usage'], dict) else {}
        for key in ('gemini', 'claude'):
            if key in usage:
                event = usage_event(stamp, usage[key], row['model_name'] if key == 'claude' else '')
                # Transcript metadata aggregates an unknown number of calls.
                events.append((*event[:3], None if key == 'gemini' else event[3]))
    # Daily messages only use _free_chat (Groq/NIM). The stored model name
    # cannot identify which provider answered; never charge them to Claude.
    # Research calls use OpenAI, not Claude. clinic_ai has no OpenAI tariff.
    for row in bounded_rows(AIResearchCall.objects.filter(started_at__gte=start, started_at__lte=now).values('started_at')):
        events.append((row['started_at'], 'openai', None, 1))
    # Each reservation is an upper bound, even on an error/unknown outcome.
    # Settled user-resource counts are not stored, so do not invent a net bill.
    for row in bounded_rows(PoliticalRead.objects.filter(started_at__gte=start, started_at__lte=now).values('started_at', 'reserved_usd')):
        events.append((row['started_at'], 'x', float(row['reserved_usd']), 1))
    return events


def total(events, provider, start, end, index=2):
    values = [e[index] for e in events if (provider is None and e[1] != 'x' or e[1] == provider) and start <= e[0] < end]
    return UNKNOWN if any(v is None for v in values) else round(sum(values), 6)


def ai_section(events, today, now):
    from news.admin_status import card, metric
    from news.council_charter import roster
    from news.council_registry import limit_key
    members = roster()
    counters = cache.get_many([limit_key((m['provider'], m['model'])) for m in members])
    rows = []
    for provider, label in AI_PROVIDERS:
        relevant = [m for m in members if m['provider'] == provider]
        counts = [counters.get(limit_key((m['provider'], m['model']))) for m in relevant]
        daily = total(events, provider, today, now + timedelta(microseconds=1), 3)
        monthly = total(events, provider, today.replace(day=1), now + timedelta(microseconds=1), 3)
        if provider in ('groq', 'nim', 'openrouter', 'hf', 'cloudflare', 'mistral', 'pllum'):
            daily = sum(counts) if counts and all(type(c) is int for c in counts) else UNKNOWN
            monthly = UNKNOWN  # expiring daily cache is not a monthly ledger
        rows.append(card(label, 'unknown', 'Liczby dotyczą utrwalonych zużyć; liczniki konsylium liczą rezerwacje prób (dzień UTC). Koszt nie obejmuje niezapisanych prób ani innych aplikacji.', metrics=[
            metric('Wywołania dziś', daily), metric('Wywołania w miesiącu', monthly),
            metric('Szacowany koszt dziś (USD)', total(events, provider, today, now + timedelta(microseconds=1)) if provider in ('anthropic', 'gemini', 'openai', 'unknown') else UNKNOWN),
            metric('Szacowany koszt miesiąca (USD)', total(events, provider, today.replace(day=1), now + timedelta(microseconds=1)) if provider in ('anthropic', 'gemini', 'openai', 'unknown') else UNKNOWN),
            metric('Próby konsylium dziś (UTC)', sum(counts) if counts and all(type(c) is int for c in counts) else UNKNOWN),
        ]))
    return card('AI i koszty', 'unknown', 'Szacunki clinic_ai.cost_usd z zapisanych zużyć i zachowanych sum KRS, nie faktury. Transkrypcje mogą łączyć wiele wywołań; data to diagnoza lub zapis materiału. Konsylium z eskalacją nadpisuje model Claude — koszt unknown. Brak pełnej historii KRS, ponowień i darmowych wywołań; darmowe pule nie dowodzą zerowego rachunku.', now, items=rows)


def refresh_openrouter():
    """Free account endpoint; never echo response bodies, headers or exceptions."""
    result = {'balance': UNKNOWN, 'checked_at': timezone.now().astimezone(WARSAW).isoformat()}
    try:
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if key:
            with requests.get('https://openrouter.ai/api/v1/credits', headers={'Authorization': 'Bearer ' + key},
                              timeout=(0.5, 0.7), allow_redirects=False) as response:
                if response.status_code == 200:
                    data = response.json().get('data', {})
                    credit, used = number(data.get('total_credits')), number(data.get('total_usage'))
                    if credit is not None and used is not None:
                        result['balance'] = round(credit - used, 6)
    except Exception:
        pass
    finally:
        cache.set('admin:openrouter:credits', result, 600)
        cache.delete('admin:openrouter:refresh')
    return result


def openrouter_balance():
    result = cache.get('admin:openrouter:credits')
    if result is not None:
        return result
    # DNS/remote latency must never be on the status endpoint's critical path.
    # A distributed short lease bounds refreshes across API workers.
    if os.environ.get('OPENROUTER_API_KEY', '').strip() and cache.add('admin:openrouter:refresh', True, 30):
        threading.Thread(target=refresh_openrouter, daemon=True, name='wallet-credits').start()
    return {'balance': UNKNOWN, 'checked_at': UNKNOWN}


PAID = ('x', 'gemini', 'anthropic')  # jedyne portfele z doładowaniami; reszta modeli działa na darmowych pulach


def provider_signals(now):
    """Brak środków rozpoznany automatycznie z odpowiedzi dostawców (402 / „credit balance”), dopóki nie przyjdzie sukces."""
    from news.clinic_models import CouncilSeat
    signals = {}
    since = now - timedelta(hours=48)
    read = PoliticalRead.objects.filter(finished_at__isnull=False).order_by('-finished_at').values('http_status', 'finished_at').first()
    if read and read['http_status'] == 402 and read['finished_at'] >= since:
        signals['x'] = 'X odrzuca odczyty wpisów: brak środków (402).'
    if CouncilSeat.objects.filter(provider='gemini', last_error__contains='402').exists():
        signals['gemini'] = 'Gemini odrzuca zapytania: brak środków (402). Wraca samo po doładowaniu.'
    failed = SpinDiagnosis.objects.filter(diagnosed_at__gte=since, error__icontains='credit balance').order_by('-diagnosed_at').values('diagnosed_at').first()
    if failed and not SpinDiagnosis.objects.filter(diagnosed_at__gt=failed['diagnosed_at'], error='').filter(
            Q(model_name__icontains='claude') | Q(model_name__icontains='sonnet') | Q(model_name__icontains='haiku')).exists():
        signals['anthropic'] = 'Anthropic odrzuca zapytania: za niskie saldo (credit balance).'
    return signals


def usd_rate(currency):
    """Ile jednostek waluty portfela kosztuje 1 USD (stały kurs z ustawień; domyślnie PLN 3,70, EUR 0,92)."""
    if currency == 'USD':
        return 1.0
    default = {'PLN': 3.7, 'EUR': 0.92}.get(currency)
    try:
        value = float(os.environ.get(f'WALLET_USD_{currency}', '') or default)
    except (TypeError, ValueError):
        return default
    return value if value and value > 0 else default


def wallet_snapshot(entries, events, now, actual, history_complete=True, signals=None):
    signals = signals or {}
    wallets = []
    for provider, label in [p for p in PROVIDERS if p[0] in PAID]:
        entry = entries.get(provider)
        row = dict(provider=provider, label=label, currency=entry.currency if entry else 'USD',
                   recorded_balance=float(entry.amount) if entry else UNKNOWN,
                   recorded_at=entry.recorded_at if entry else UNKNOWN, spent_since=UNKNOWN,
                   estimated_balance=UNKNOWN, actual_balance=actual['balance'] if provider == 'openrouter' else UNKNOWN,
                   actual_currency='USD', actual_checked_at=actual['checked_at'] if provider == 'openrouter' else UNKNOWN,
                   days_remaining=UNKNOWN, status='unknown', note='Wpisz saldo odczytane u dostawcy i datę pomiaru.')
        if entry:
            row['note'] = 'Szacunek z zapisanych zużyć; brak historii wszystkich prób i wydatków poza projektem.'
            fx = usd_rate(entry.currency)
            if fx is None:
                row['note'] = 'Koszty zapisano w USD. Brak kursu walut — szacowane saldo i liczba dni są nieznane.'
            elif provider in ('x', 'anthropic', 'gemini') and history_complete:
                spent = total(events, provider, entry.recorded_at, now + timedelta(microseconds=1))
                rate = total(events, provider, now - timedelta(days=7), now + timedelta(microseconds=1))
                # Wydatki liczymy w USD; saldo wpisane w złotych/euro przeliczamy stałym kursem z ustawień.
                spent = round(spent * fx, 6) if spent != UNKNOWN else spent
                rate = round(rate * fx, 6) if rate != UNKNOWN else rate
                # Unattributable paid usage cannot safely be excluded from a wallet.
                if provider != 'x' and any(e[1] == 'unknown' and e[0] >= entry.recorded_at for e in events):
                    spent = UNKNOWN
                if provider != 'x' and any(e[1] == 'unknown' and e[0] >= now - timedelta(days=7) for e in events):
                    rate = UNKNOWN
                row['spent_since'] = spent
                if spent != UNKNOWN:
                    row['estimated_balance'] = round(float(entry.amount) - spent, 6)
                    if rate != UNKNOWN and rate > 0:
                        row['days_remaining'] = max(0, round(row['estimated_balance'] / (rate / 7), 1))
                    row['status'] = ('error' if row['estimated_balance'] <= 0 else 'warn'
                                     if row['days_remaining'] != UNKNOWN and row['days_remaining'] < 7 else 'ok')
                if entry.currency != 'USD':
                    row['note'] += f' Wydatki przeliczone kursem 1 USD = {fx} {entry.currency} (WALLET_USD_{entry.currency}).'
                if provider == 'x':
                    row['note'] = 'Od salda odejmujemy górny szacunek: pełne rezerwacje PoliticalRead (także nieudane). Dni według ostatnich 7×24 h.'
                if provider == 'gemini':
                    # KRS only stores daily totals, so spending before/after
                    # an intraday balance observation cannot be apportioned.
                    local = entry.recorded_at.astimezone(WARSAW)
                    day_cost = number(cache.get(f'krs-agent-spent:{local.date().isoformat()}'))
                    if day_cost and (local.hour or local.minute or local.second or local.microsecond):
                        row.update(spent_since=UNKNOWN, estimated_balance=UNKNOWN, days_remaining=UNKNOWN, status='unknown')
                    row['note'] += ' KRS: tylko zachowane sumy dzienne z cache; brak podziału godzinowego. Wygasłej historii KRS nie odtworzono.'
            else:
                row['note'] = 'Brak pełnej ewidencji wydatków tego dostawcy. Ręczne saldo nie jest bieżącym saldem.'
        if provider == 'openrouter':
            row['note'] += ' Saldo API w USD; cache 10 min, pierwszy odczyt w tle. API może wymagać klucza zarządzającego.'
            if actual['balance'] != UNKNOWN:
                row['status'] = 'error' if actual['balance'] <= 0 else 'ok'
        if provider in signals:
            row.update(status='error', signal=signals[provider], note=f"{signals[provider]} {row['note']}")
        wallets.append(row)
    return wallets


def finance_snapshot(now, today):
    latest = WalletBalance.objects.filter(provider=OuterRef('provider'), recorded_at__lte=now).values('pk')[:1]
    entries = {row.provider: row for row in WalletBalance.objects.filter(pk=Subquery(latest))}
    start = min([today.replace(day=1), today - timedelta(days=7)] +
                [e.recorded_at for e in entries.values() if e.provider in ('x', 'gemini', 'anthropic') and usd_rate(e.currency)])
    complete = True
    try:
        events = recorded_events(start, now)
    except HistoryLimit:
        events, complete = [], False
    # KRS retains ~30 h of daily totals. Include available observations, with
    # missing older history explicitly described as outside the estimate.
    for offset in range(0, 8):
        day = today - timedelta(days=offset)
        cost = number(cache.get(f'krs-agent-spent:{day.date().isoformat()}'))
        if cost is not None and cost > 0:
            events.append((day, 'gemini', cost, None))
    series = {'key': 'costs', 'label': 'Koszty AI (zapisane zużycia)', 'unit': 'USD', 'points': []}
    for n in range(-6, 1):
        day = today + timedelta(days=n)
        series['points'].append({'date': day.date().isoformat(), 'value': total(events, None, day, day + timedelta(days=1)) if complete else UNKNOWN})
    from news.admin_status import card
    section = ai_section(events, today, now) if complete else card('AI i koszty', description='Historia przekracza limit 5000 rekordów jednego typu; podaj nowszy pomiar salda. Nie pokazujemy niepełnych sum.')
    return {'section': section,
            'wallets': wallet_snapshot(entries, events, now, {'balance': UNKNOWN, 'checked_at': UNKNOWN}, complete, provider_signals(now)), 'series': series,
            'kpi': {'key': 'costs', 'label': 'Koszty AI · szacunek', 'unit': 'USD',
                    'today': total(events, None, today, now + timedelta(microseconds=1)) if complete else UNKNOWN,
                    'yesterday': total(events, None, today - timedelta(days=1), today) if complete else UNKNOWN}}


class WalletSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0'))
    recorded_at = serializers.DateTimeField(required=True, default_timezone=WARSAW)

    class Meta:
        model = WalletBalance
        fields = ['id', 'provider', 'amount', 'currency', 'recorded_at']
        read_only_fields = ['id']

    def validate_recorded_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('Data salda nie może być w przyszłości.')
        return value


@never_cache
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_wallets(request):
    serializer = WalletSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=201)
