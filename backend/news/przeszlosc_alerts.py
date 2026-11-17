"""Alerty e-mail przeszłość.today (sprint 1): obserwuj temat albo osobę publiczną.

Zapis: adres + temat albo osoba, zgoda, podwójne potwierdzenie (link w e-mailu). Codziennie o 7:00 jeden list na adres
ze wszystkimi nowościami (wpisy, diagnozy Dr. Spina, dokumenty Sejmu, głosowania, zmiany w KRS) dla każdego alertu.
Wypisanie jednym kliknięciem (link w treści i nagłówek List-Unsubscribe). Bez śledzenia: zwykły tekst, bez pikseli,
bez parametrów w linkach. Odpowiedź na zapis jest zawsze taka sama - nie zdradzamy, czy adres już coś obserwuje.
"""
import logging
import os
import secrets
from datetime import timedelta
from urllib.parse import quote

from news import krs
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from news.przeszlosc_models import PrzeszloscAlert

logger = logging.getLogger(__name__)

CONSENT_VERSION = '2026-10-06'
MAX_PER_EMAIL = 20
PER_ALERT = 10
RESEND_AFTER = timedelta(minutes=10)
CHECK_EMAIL = {'status': 'check_email', 'detail': 'Sprawdź skrzynkę - wysłaliśmy link potwierdzający. Bez potwierdzenia nic nie wyślemy.'}


class AlertThrottle(AnonRateThrottle):
    scope = 'przeszlosc_alerts'
    rate = '5/hour'


class TokenThrottle(AnonRateThrottle):
    scope = 'przeszlosc_alert_token'
    rate = '30/hour'


def site():
    return 'https://' + os.environ.get('PRZESZLOSC_DOMAIN', 'przeszlosc.today')


def api_site():
    return 'https://' + os.environ.get('PRZESZLOSC_API_DOMAIN', os.environ.get('PRZESZLOSC_DOMAIN', 'przeszlosc.today'))


def subject_url(alert):
    if alert.kind == 'topic':
        return f'{site()}/przeszlosc?q={quote(alert.query)}'
    from news.przeszlosc_osoba import slug
    return f'{site()}/przeszlosc/osoba/{slug(alert.figure)}'


def unsubscribe_url(alert, everything=False):
    return f'{site()}/przeszlosc/alerty?wypisz={alert.token}' + ('&wszystkie=1' if everything else '')


def one_click_url(alert):
    return f'{api_site()}/api/przeszlosc/alerty/wypisz/?t={alert.token}&wszystkie=1'


def send_confirmation(alert_id):
    from news.account_mail import send_account_mail
    alert = PrzeszloscAlert.objects.select_related('figure').filter(pk=alert_id, status='pending').first()
    if not alert:
        return 'skipped'
    what = f'temat „{alert.query}”' if alert.kind == 'topic' else f'osobę publiczną: {alert.figure.canonical_name}'
    body = ('Dzień dobry,\n\n'
            f'ktoś (mamy nadzieję, że Ty) chce obserwować w przeszłość.today {what}.\n'
            'Po potwierdzeniu codziennie o 7:00 dostaniesz jeden list z nowościami: wpisy, diagnozy Dr. Spina, dokumenty Sejmu, '
            'głosowania i zmiany w KRS. Gdy nic nowego nie ma, nic nie wysyłamy.\n\n'
            f'Potwierdź tutaj:\n{site()}/przeszlosc/alerty?potwierdz={alert.token}\n\n'
            'Jeśli to nie Ty, zignoruj tę wiadomość. Bez potwierdzenia nie wyślemy nic więcej.\n'
            f'Rezygnacja w każdej chwili: {unsubscribe_url(alert)}\n\n'
            'Nie śledzimy otwarć ani kliknięć.\n'
            'przeszłość.today prowadzi iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań')
    if not send_account_mail(alert.email, 'Potwierdź obserwowanie - przeszłość.today', body):
        return 'failed'
    PrzeszloscAlert.objects.filter(pk=alert.pk).update(confirmation_sent_at=timezone.now())
    return 'sent'


def _queue(alert_id):
    from news.tasks import przeszlosc_alert_confirmation_task
    transaction.on_commit(lambda: przeszlosc_alert_confirmation_task.delay(alert_id))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AlertThrottle])
def subscribe_view(request):
    """POST /api/przeszlosc/alerty/ {email, kind: topic|person, q | figure, consent: true}."""
    from news.przeszlosc import enabled, terms
    from news.przeszlosc_osoba import resolve
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    if request.data.get('website'):  # pole-pułapka dla botów
        return Response(CHECK_EMAIL)
    email = str(request.data.get('email', '')).strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return Response({'detail': 'Podaj poprawny adres e-mail.'}, status=400)
    if request.data.get('consent') is not True:
        return Response({'detail': 'Zaznacz zgodę na codzienne powiadomienia.'}, status=400)
    from news.przeszlosc_dostep import has, locked
    if not has('alerts', request, email):
        return locked('alerts')
    kind = request.data.get('kind')
    figure, query = None, ''
    if kind == 'topic':
        query = ' '.join(str(request.data.get('q', '')).split())[:120]
        if not terms(query):
            return Response({'detail': 'Podaj temat (co najmniej 3 znaki).'}, status=400)
        key = 'topic:' + query.lower()
    elif kind == 'person':
        figure = resolve(request.data.get('figure'))
        if figure is None:
            return Response({'detail': 'Nie ma takiej osoby publicznej w rejestrze.'}, status=400)
        key = f'person:{figure.pk}'
    else:
        return Response({'detail': 'Wybierz temat albo osobę.'}, status=400)
    now = timezone.now()
    with transaction.atomic():
        alert = PrzeszloscAlert.objects.select_for_update().filter(email=email, key=key).first()
        if alert is None:
            if PrzeszloscAlert.objects.filter(email=email).exclude(status='unsubscribed').count() >= MAX_PER_EMAIL:
                return Response(CHECK_EMAIL)  # limit na adres; odpowiedź taka sama
            alert = PrzeszloscAlert.objects.create(email=email, key=key, kind=kind, query=query, figure=figure,
                                                   token=secrets.token_urlsafe(32), consent_version=CONSENT_VERSION)
        elif alert.status == 'confirmed':
            return Response(CHECK_EMAIL)
        elif alert.status == 'pending' and alert.confirmation_sent_at and now - alert.confirmation_sent_at < RESEND_AFTER:
            return Response(CHECK_EMAIL)
        else:
            alert.status, alert.token, alert.unsubscribed_at = 'pending', secrets.token_urlsafe(32), None
            alert.consent_version, alert.query = CONSENT_VERSION, query or alert.query
            alert.save(update_fields=['status', 'token', 'unsubscribed_at', 'consent_version', 'query'])
        _queue(alert.pk)
    return Response(CHECK_EMAIL)


def _token(request):
    token = str(request.query_params.get('t') or request.data.get('token') or '').strip()
    return PrzeszloscAlert.objects.select_related('figure').filter(token=token).first() if len(token) >= 20 else None


def _describe(alert):
    return {'kind': alert.kind, 'label': alert.label, 'url': subject_url(alert).removeprefix(site())}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([TokenThrottle])
def confirm_view(request):
    alert = _token(request)
    if alert is None or alert.status == 'unsubscribed':
        return Response({'detail': 'Link wygasł albo jest niepoprawny. Zapisz się ponownie.'}, status=404)
    if alert.status == 'pending':
        alert.status, alert.confirmed_at = 'confirmed', timezone.now()
        alert.save(update_fields=['status', 'confirmed_at'])
    return Response({'status': 'confirmed', **_describe(alert)})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([TokenThrottle])
def unsubscribe_view(request):
    """Wypisanie jednym kliknięciem; ?wszystkie=1 albo wszystkie=true wypisuje adres ze wszystkich alertów (RFC 8058)."""
    alert = _token(request)
    if alert is None:
        return Response({'detail': 'Link jest niepoprawny albo adres już wypisano.'}, status=404)
    everything = str(request.query_params.get('wszystkie') or request.data.get('wszystkie') or '').lower() in ('1', 'true')
    rows = PrzeszloscAlert.objects.filter(email=alert.email) if everything else PrzeszloscAlert.objects.filter(pk=alert.pk)
    count = rows.exclude(status='unsubscribed').update(status='unsubscribed', unsubscribed_at=timezone.now())
    return Response({'status': 'unsubscribed', 'count': count, **_describe(alert)})


# --- dzienny list ---
def _short(text, n=180):
    text = ' '.join((text or '').split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def topic_items(alert, since):
    from news.przeszlosc import topic_graph
    kinds = {'statement': 'Wpis', 'record': 'Sejm', 'media': 'Artykuł', 'diagnosis': 'Diagnoza Dr. Spina'}
    floor = (since - timedelta(days=1)).date().isoformat()
    sent = set(alert.sent_ids or [])
    nodes = [n for n in topic_graph(alert.query)['nodes'] if n['kind'] in kinds and (n.get('date') or '') >= floor and n['id'] not in sent]
    nodes.sort(key=lambda n: n.get('date') or '', reverse=True)
    return [{'id': n['id'], 'date': n.get('date'), 'kind': kinds[n['kind']] + (f" · {n['sub']}" if n.get('sub') and n['kind'] != 'diagnosis' else ''),
             'text': (f"spin {n.get('intensity')}/100 · " if n['kind'] == 'diagnosis' else '') + _short(n.get('text') or n['label']),
             'url': n.get('url') or ''} for n in nodes]


def person_items(alert, since):
    from news.clinic import published_diagnoses
    from news.political_models import PoliticalPost, PublicFigureOrganisationRelation
    from news.przeszlosc_osoba import RECORD_LABEL, VOTE_LABEL, _ballots, _records, mp_identities, vote_url, x_accounts
    figure = alert.figure
    sent = set(alert.sent_ids or [])
    items = []
    accounts = [a for a, _ in x_accounts(figure)]
    diagnosed = {}
    fresh = Q(reviewed_at__gt=since) | Q(diagnosed_at__gt=since - timedelta(days=2))
    for d in published_diagnoses().filter(fresh, post__account__in=accounts).select_related('post'):
        diagnosed[d.post_id] = d
        items.append({'id': f'diagnosis:{d.pk}', 'date': d.post.published_at.date().isoformat(), 'kind': 'Diagnoza Dr. Spina',
                      'text': f'spin {d.intensity}/100 · {_short(d.headline or d.post.text)}', 'url': f'https://spin.clinic/klinika/{d.pk}'})
    for p in PoliticalPost.objects.filter(account__in=accounts, available=True, fetched_at__gt=since).order_by('-published_at')[:50]:
        if p.pk not in diagnosed:
            items.append({'id': f'post:{p.pk}', 'date': p.published_at.date().isoformat(), 'kind': 'Wpis na X', 'text': _short(p.text), 'url': p.url})
    identities = mp_identities(figure)
    for person in _records(figure, identities).filter(record__fetched_at__gt=since).select_related('record')[:50]:
        r = person.record
        items.append({'id': f'record:{r.pk}', 'date': r.date.isoformat() if r.date else None, 'kind': RECORD_LABEL.get(r.kind, 'Dokument Sejmu'),
                      'text': _short(r.title), 'url': r.source_url})
    for b in _ballots(identities).filter(voting__article__created_at__gt=since).select_related('voting__article')[:50]:
        when = b.voting.article.published_date
        items.append({'id': f'vote:{b.voting_id}', 'date': when.date().isoformat() if when else None,
                      'kind': f"Głosowanie: {VOTE_LABEL.get(b.vote, 'inne')}", 'text': _short(b.voting.article.title), 'url': vote_url(b.voting)})
    for rel in (PublicFigureOrganisationRelation.objects.filter(public_figure=figure, verification_status='confirmed', updated_at__gt=since)
                .select_related('organisation')):
        items.append({'id': f'krs:{rel.pk}:{rel.relation_status}', 'date': (rel.since or rel.updated_at.date()).isoformat(),
                      'kind': 'KRS (kontekst, nie dowód)', 'text': f'{rel.organisation.name}: {rel.organ or rel.public_role}'
                      + (' (historyczna)' if rel.relation_status == 'former' else ''), 'url': krs.official_register_url(rel.organisation.official_register_url)})
    items = [i for i in items if i['id'] not in sent]
    items.sort(key=lambda i: i['date'] or '', reverse=True)
    return items


def digest_for(alerts, now):
    """Treść jednego listu dla adresu i lista (alert, wysłane id). Pusty list, gdy nic nowego."""
    sections, updates = [], []
    for alert in alerts:
        since = alert.last_sent_at or alert.confirmed_at or now - timedelta(days=1)
        try:
            items = topic_items(alert, since) if alert.kind == 'topic' else person_items(alert, since)
        except Exception:  # jeden zepsuty alert nie blokuje pozostałych
            logger.warning('przeszlosc alert %s: items failed', alert.pk, exc_info=False)
            continue
        if not items:
            continue
        title = f'Temat: {alert.query}' if alert.kind == 'topic' else f'Osoba: {alert.figure.canonical_name}'
        lines = [f'== {title} ({len(items)} {"nowa pozycja" if len(items) == 1 else "nowe pozycje" if 2 <= len(items) % 10 <= 4 and not 12 <= len(items) % 100 <= 14 else "nowych pozycji"}) ==']
        for item in items[:PER_ALERT]:
            lines.append(f"- {item['date'] or 'bez daty'} · {item['kind']}: {item['text']}")
            if item['url']:
                lines.append(f"  {item['url']}")
        if len(items) > PER_ALERT:
            lines.append(f'  i jeszcze {len(items) - PER_ALERT} na stronie.')
        lines.append(f'Całość: {subject_url(alert)}')
        lines.append(f'Przestań obserwować: {unsubscribe_url(alert)}')
        sections.append('\n'.join(lines))
        updates.append((alert, [i['id'] for i in items]))
    if not sections:
        return '', []
    first = alerts[0]
    body = (f'Dzień dobry,\n\nnowości w przeszłość.today ({now.astimezone(timezone.get_current_timezone()).date().isoformat()}).\n\n'
            + '\n\n'.join(sections)
            + '\n\nFunkcje w KRS to kontekst osoby, nie dowód związku z tematem ani winy. Każda pozycja prowadzi do źródła.\n'
            + f'Wypisz się ze wszystkich alertów: {unsubscribe_url(first, everything=True)}\n'
            + 'Nie śledzimy otwarć ani kliknięć. przeszłość.today prowadzi iapply sp. z o.o.')
    return body, updates


def send_digests(now=None, dry_run=False):
    """Codziennie o 7:00: jeden list na adres. Powtórne uruchomienie tego samego dnia nic nie wysyła."""
    from news.account_mail import send_account_mail
    now = now or timezone.now()
    by_email = {}
    for alert in PrzeszloscAlert.objects.filter(status='confirmed').select_related('figure').order_by('email', 'created_at'):
        if alert.kind == 'person' and (alert.figure is None or alert.figure.archived):
            continue
        by_email.setdefault(alert.email, []).append(alert)
    report = {'emails': 0, 'sent': 0, 'empty': 0, 'failed': 0, 'skipped': 0}
    for email, alerts in by_email.items():
        report['emails'] += 1
        alerts = [a for a in alerts if not a.last_sent_at or now - a.last_sent_at > timedelta(hours=20)][:MAX_PER_EMAIL]
        if not alerts:
            report['skipped'] += 1
            continue
        body, updates = digest_for(alerts, now)
        if not body:
            report['empty'] += 1
            continue
        if dry_run:
            report['sent'] += 1
            report.setdefault('preview', body)
            continue
        headers = {'List-Unsubscribe': f'<{one_click_url(alerts[0])}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
        if not send_account_mail(email, 'Nowości w obserwowanych tematach - przeszłość.today', body, headers=headers):
            report['failed'] += 1
            continue
        report['sent'] += 1
        for alert, ids in updates:
            alert.last_sent_at = now
            alert.sent_ids = (list(alert.sent_ids or []) + ids)[-1000:]
            alert.save(update_fields=['last_sent_at', 'sent_ids'])
    return report
