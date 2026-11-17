"""Strażnik terminów zewnętrznych (Z3, przegląd architekta 7.10): serwis nie znika z powodów poza kodem.

Codziennie 6:15 (terminy_task), bez AI:
- domeny (RDAP przez rdap.org): data wygaśnięcia i status (pendingDelete, clientHold, serverHold, redemptionPeriod = krytyczny);
- TLS: dni do końca certyfikatu każdego hosta;
- DNS: rekord A spin.clinic i przeszlosc.today wskazuje serwer (EXPECTED_SERVER_IP, domyślnie 148.113.242.109);
- salda: OpenRouter (GET /api/v1/credits), X (GET /2/usage/tweets); pozostali dostawcy: „sprawdź ręcznie raz w miesiącu”;
- token GitHub do Issues: fine-grained ważny 90 dni od GITHUB_ISSUES_TOKEN_CREATED (albo od pierwszego zauważenia);
- Codex: data CODEX_AVAILABLE_FROM (informacja).
Progi 30/14/3 dni: ostrzeżenie (<= 30), krytyczny (<= 3 albo zły status, albo DNS nie wskazuje serwera). Przy przekroczeniu
każdego progu jeden ważny mail do właściciela (important=True), alarm Dyżurnego (check_terminy, bez sieci, ze stanu)
i sekcja w Raporcie pętli. Naprawa automatyczna nie jest tu możliwa (domena, pieniądze, konta) - dlatego z pełną instrukcją."""
import hashlib
import logging
import os
import socket
import ssl
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

STATE_KEY = 'terminy-zewnetrzne'
DOMAINS = ('spin.clinic', 'przeszlosc.today', 'zbudujmi.com', 'iapply.pl')
DNS_HOSTS = ('spin.clinic', 'przeszlosc.today')
DEFAULT_IP = '148.113.242.109'
THRESHOLDS = (30, 14, 3)
TOKEN_DAYS = 90
BAD_STATUS = ('pending delete', 'pendingdelete', 'client hold', 'clienthold', 'server hold', 'serverhold', 'redemption period',
              'redemptionperiod', 'inactive')
MANUAL = (('Gemini', 'https://aistudio.google.com/usage'), ('Groq', 'https://console.groq.com/settings/billing'),
          ('Anthropic', 'https://console.anthropic.com/settings/billing'), ('Mistral', 'https://console.mistral.ai/usage'),
          ('Inception', 'https://platform.inceptionlabs.ai/'), ('Cloudflare (zbudujmi.com DNS)', 'https://dash.cloudflare.com/'))
TIMEOUT = (5, 15)
RDAP = 'https://rdap.org/domain/{domain}'
OPENROUTER_CREDITS = 'https://openrouter.ai/api/v1/credits'
X_USAGE = 'https://api.x.com/2/usage/tweets'
STALE = timedelta(hours=48)


def expected_ip():
    return os.environ.get('EXPECTED_SERVER_IP', DEFAULT_IP).strip() or DEFAULT_IP


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


# --- sondy (każda osobno, wynik albo wyjątek) -------------------------------------------------------------------

def parse_rdap(data):
    """Z odpowiedzi RDAP: data wygaśnięcia (expiration) i lista statusów (małe litery)."""
    expires = None
    for event in data.get('events') or []:
        if str(event.get('eventAction', '')).lower() == 'expiration' and event.get('eventDate'):
            try:
                expires = datetime.fromisoformat(str(event['eventDate']).replace('Z', '+00:00'))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=dt_timezone.utc)
            except ValueError:
                expires = None
    return {'expires': expires, 'status': [str(s).lower() for s in data.get('status') or []]}


def rdap(domain):
    response = requests.get(RDAP.format(domain=domain), headers={'Accept': 'application/rdap+json'}, timeout=TIMEOUT, allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f'RDAP HTTP {response.status_code}')
    return parse_rdap(response.json())


def tls_expiry(host):
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=10) as sock, context.wrap_socket(sock, server_hostname=host) as tls:
        cert = tls.getpeercert()
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), dt_timezone.utc)


def dns_a(host):
    return sorted({info[4][0] for info in socket.getaddrinfo(host, 443, socket.AF_INET)})


def openrouter_credits():
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        return None
    response = requests.get(OPENROUTER_CREDITS, headers={'Authorization': 'Bearer ' + key}, timeout=TIMEOUT)
    if response.status_code != 200:
        raise RuntimeError(f'OpenRouter HTTP {response.status_code}')
    data = response.json().get('data') or {}
    return round(float(data.get('total_credits') or 0) - float(data.get('total_usage') or 0), 2)


def x_usage():
    key = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
    if not key:
        return None
    response = requests.get(X_USAGE, headers={'Authorization': 'Bearer ' + key}, timeout=TIMEOUT)
    if response.status_code != 200:
        raise RuntimeError(f'X HTTP {response.status_code}')
    data = response.json().get('data') or {}
    used, cap = int(data.get('project_usage') or 0), int(data.get('project_cap') or 0)
    return {'used': used, 'cap': cap, 'pct': round(100 * used / cap) if cap else None, 'reset_day': data.get('cap_reset_day')}


# --- ocena --------------------------------------------------------------------------------------------------------

def days_left(at, now):
    """Dni kalendarzowe do terminu (czas lokalny), nie pełne doby."""
    if at is None:
        return None
    tz = timezone.get_current_timezone()
    return (at.astimezone(tz).date() - now.astimezone(tz).date()).days


def stage(days):
    """Próg przekroczony: 3, 14, 30 albo None (poza progami)."""
    if days is None:
        return None
    return next((t for t in sorted(THRESHOLDS) if days <= t), None)


def level_for(days, bad=False):
    if bad or (days is not None and days <= 3):
        return 'critical'
    return 'warning' if days is not None and days <= 30 else 'ok'


def item(key, label, kind, level='ok', days=None, detail='', instruction='', **extra):
    return {'key': key, 'label': label, 'kind': kind, 'level': level, 'days': days, 'detail': detail, 'instruction': instruction[:300], **extra}


def _state():
    from news.models import RepairerState
    row, _ = RepairerState.objects.get_or_create(key=STATE_KEY)
    return row


def snapshot():
    from news.models import RepairerState
    row = RepairerState.objects.filter(key=STATE_KEY).first()
    return dict(row.data or {}) if row else {}


def github_token_created(now, data):
    """Data utworzenia tokena: GITHUB_ISSUES_TOKEN_CREATED (YYYY-MM-DD) albo pierwsze zauważenie tego tokena (skrót, nie wartość)."""
    token = os.environ.get('GITHUB_ISSUES_TOKEN', '').strip()
    if not token:
        return None, data
    env = os.environ.get('GITHUB_ISSUES_TOKEN_CREATED', '').strip()
    if env:
        try:
            created = datetime.fromisoformat(env)
            return created if created.tzinfo else created.replace(tzinfo=dt_timezone.utc), data
        except ValueError:
            pass
    digest = hashlib.sha256(token.encode()).hexdigest()[:12]
    if data.get('github_token_hash') != digest or not data.get('github_token_seen'):
        data = {**data, 'github_token_hash': digest, 'github_token_seen': now.isoformat()}
    return datetime.fromisoformat(data['github_token_seen']), data


def collect(now, data):
    """Wszystkie pozycje; każda sonda osobno, błąd sondy = poziom 'unknown' (bez alarmu, widoczny w raporcie)."""
    out = []
    local_tz = timezone.get_current_timezone()

    def fmt(at):
        return at.astimezone(local_tz).strftime('%d.%m.%Y') if at else '?'
    for domain in DOMAINS:
        try:
            info = rdap(domain)
            days = days_left(info['expires'], now)
            bad = any(s in BAD_STATUS for s in info['status'])
            detail = f"domena wygasa {fmt(info['expires'])}" + (f' ({days} dni)' if days is not None else '') + \
                     (f"; status: {', '.join(info['status'])}" if bad else '')
            out.append(item(f'domena:{domain}', domain, 'domena', level_for(days, bad), days, detail,
                            f'Odnów domenę {domain} u rejestratora (Key-Systems przez resellera; zbudujmi.com: Cloudflare) i sprawdź e-mail abonenta - '
                            'zawieszenie 28.09 było przez niezweryfikowany adres.', bad=bad))
        except Exception as error:  # noqa: BLE001 - jedna sonda nie zatrzymuje reszty
            out.append(item(f'domena:{domain}', domain, 'domena', 'unknown', detail=f'RDAP nie odpowiedział ({type(error).__name__})'))
        try:
            expires = tls_expiry(domain)
            days = days_left(expires, now)
            out.append(item(f'tls:{domain}', domain, 'tls', level_for(days if days is not None and days <= 14 else None), days,
                            f'TLS do {fmt(expires)} ({days} dni)', 'Caddy odnawia certyfikaty sam; sprawdź logi: docker compose logs caddy --tail 50 '
                            'oraz czy porty 80/443 są otwarte i DNS wskazuje serwer.'))
        except Exception as error:  # noqa: BLE001
            out.append(item(f'tls:{domain}', domain, 'tls', 'unknown', detail=f'TLS nie sprawdzony ({type(error).__name__})'))
    for host in DNS_HOSTS:
        try:
            ips = dns_a(host)
            ok = expected_ip() in ips
            out.append(item(f'dns:{host}', host, 'dns', 'ok' if ok else 'critical', None,
                            f"DNS A -> {', '.join(ips) or 'brak'}" + ('' if ok else f' (oczekiwano {expected_ip()})'),
                            f'Ustaw rekord A {host} na {expected_ip()} u operatora DNS; sprawdź, czy domena nie jest zawieszona (status RDAP).', ok=ok))
        except Exception as error:  # noqa: BLE001
            out.append(item(f'dns:{host}', host, 'dns', 'critical', None, f'DNS nie odpowiada ({type(error).__name__})',
                            'Domena nie rozwiązuje się: sprawdź status RDAP i rejestratora.'))
    try:
        credits = openrouter_credits()
        if credits is None:
            out.append(item('saldo:openrouter', 'OpenRouter', 'saldo', 'na', detail='brak klucza'))
        else:
            warn = _float('OPENROUTER_WARN_USD', 2)
            out.append(item('saldo:openrouter', 'OpenRouter', 'saldo', 'warning' if credits < warn else 'ok', None,
                            f'kredyty {credits:.2f} USD' + (f' (próg {warn:g})' if credits < warn else ''),
                            'Doładuj OpenRouter: https://openrouter.ai/settings/credits (10 USD wystarcza na miesiąc dociśnięć).', value=credits))
    except Exception as error:  # noqa: BLE001
        out.append(item('saldo:openrouter', 'OpenRouter', 'saldo', 'unknown', detail=f'nie sprawdzono ({type(error).__name__})'))
    try:
        usage = x_usage()
        if usage is None:
            out.append(item('saldo:x', 'X (odczyty)', 'saldo', 'na', detail='brak klucza'))
        else:
            warn = _float('X_BUDGET_WARN_PCT', 80)
            pct = usage['pct']
            out.append(item('saldo:x', 'X (odczyty)', 'saldo', 'warning' if pct is not None and pct >= warn else 'ok', None,
                            f"zużycie {usage['used']}/{usage['cap']} wpisów" + (f' ({pct}%)' if pct is not None else '') +
                            (f", reset dnia {usage['reset_day']}" if usage.get('reset_day') else ''),
                            'Limit X na wyczerpaniu: podnieś plan albo doładuj w https://developer.x.com/en/portal/dashboard; '
                            'do czasu resetu zbieracz czyta rzadziej (X według wartości konta).', value=pct))
    except Exception as error:  # noqa: BLE001
        out.append(item('saldo:x', 'X (odczyty)', 'saldo', 'unknown', detail=f'nie sprawdzono ({type(error).__name__})'))
    created, data = github_token_created(now, data)
    if created:
        expires = created + timedelta(days=TOKEN_DAYS)
        days = days_left(expires, now)
        out.append(item('token:github', 'Token GitHub (Issues)', 'token', level_for(days), days, f'ważny do {fmt(expires)} ({days} dni)',
                        'Wygeneruj nowy fine-grained token (repo spinaker, Issues: Read and write) na https://github.com/settings/personal-access-tokens, '
                        'wklej GITHUB_ISSUES_TOKEN i GITHUB_ISSUES_TOKEN_CREATED=RRRR-MM-DD do .env.production, potem '
                        'docker compose --env-file .env.production -f deploy/docker-compose.production.yml up -d --force-recreate backend worker beat'))
    else:
        out.append(item('token:github', 'Token GitHub (Issues)', 'token', 'na', detail='brak tokena'))
    try:
        from news.dyrygent import CODEX_BACK
        back = datetime.fromisoformat(CODEX_BACK).replace(tzinfo=dt_timezone.utc)
        days = days_left(back, now)
        out.append(item('codex', 'Codex', 'info', 'ok', None, 'dostępny' if days is None or days < 0 else f'limit do {fmt(back)} ({days} dni)'))
    except Exception:  # noqa: BLE001
        pass
    for label, link in MANUAL:
        out.append(item(f'manual:{label}', label, 'manual', 'manual', detail=f'sprawdź ręcznie raz w miesiącu: {link}'))
    return out, data


def _mail(subject, body):
    try:
        from news.raport_petli import recipient
        from news.social_publish import _mail as send
        to = recipient()
        return bool(to) and send(to, subject, body, important=True)
    except Exception:  # noqa: BLE001 - poczta nie zatrzymuje kontroli
        return False


def notify(items, data, now):
    """Jeden ważny mail na przekroczony próg (30, 14, 3) każdej pozycji; zły status i DNS: mail przy każdej zmianie na gorsze."""
    mailed = dict(data.get('mailed') or {})
    due = []
    for it in items:
        if it['level'] not in ('warning', 'critical'):
            mailed.pop(it['key'], None)
            continue
        current = stage(it['days']) if it['days'] is not None else 'now'
        if current is None and it['level'] == 'warning':
            current = 'warn'
        if mailed.get(it['key']) == str(current):
            continue
        mailed[it['key']] = str(current)
        due.append(it)
    if due:
        local = now.astimezone(timezone.get_current_timezone())
        lines = [f'Strażnik terminów zewnętrznych spin.clinic ({local:%d.%m %H:%M}):', '']
        for it in due:
            lines += [f"[{'KRYTYCZNY' if it['level'] == 'critical' else 'UWAGA'}] {it['label']}: {it['detail']}", f"  Co zrobić: {it['instruction']}", '']
        lines.append('Pełna tabela: python manage.py terminy_zewnetrzne · Panel: https://spin.clinic/panel')
        worst = 'KRYTYCZNY' if any(it['level'] == 'critical' for it in due) else 'uwaga'
        _mail(f"spin.clinic · Terminy zewnętrzne: {worst} - {due[0]['label']}" + (f' (+{len(due) - 1})' if len(due) > 1 else ''), '\n'.join(lines))
    return {**data, 'mailed': mailed}, len(due)


def run(now=None):
    now = now or timezone.now()
    row = _state()
    data = dict(row.data or {})
    items, data = collect(now, data)
    data, mails = notify(items, data, now)
    row.data = {**data, 'checked_at': now.isoformat(),
                'items': [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in it.items()} for it in items]}
    row.save(update_fields=['data'])
    levels = [it['level'] for it in items]
    return {'status': 'ok', 'produced': 1, 'items': len(items), 'critical': levels.count('critical'), 'warning': levels.count('warning'),
            'unknown': levels.count('unknown'), 'mails': mails}


# --- Dyżurny i Raport pętli (bez sieci) ---------------------------------------------------------------------------

def check_terminy(ctx):
    from news.duty import alarm
    from news.repairer import stamp
    data = snapshot()
    if not data.get('checked_at'):
        return []
    checked = stamp(data['checked_at']) or ctx.now
    out = []
    if ctx.now - checked > STALE:
        out.append(alarm('terminy:stale', 'warning', 'Terminy zewnętrzne: kontrola nie działa od ponad 48 h', {'checked_at': data['checked_at']},
                         checked, 'Sprawdź zadanie terminy-daily (6:15) w mapie agentów.'))
    for it in data.get('items') or []:
        if it.get('level') in ('warning', 'critical'):
            out.append(alarm(f"terminy:{it['key']}"[:180], it['level'], f"Terminy zewnętrzne: {it['label']} - {it['detail']}"[:240],
                             {'kind': it.get('kind'), 'days': it.get('days'), 'detail': it.get('detail')}, checked,
                             it.get('instruction') or 'Sprawdź tabelę: manage.py terminy_zewnetrzne.'))
    return out


def report_lines(now=None):
    """Sekcja Raportu pętli: jedna linia na domenę (domena, TLS, DNS), potem salda, token, Codex i lista „ręcznie”."""
    from news.repairer import stamp
    data = snapshot()
    if not data.get('checked_at'):
        return ['Terminy zewnętrzne: jeszcze nie sprawdzono (pierwszy bieg 6:15).']
    at = stamp(data['checked_at'])
    local = at.astimezone(timezone.get_current_timezone()) if at else None
    by_key = {it['key']: it for it in data.get('items') or []}
    mark = {'critical': ' [KRYTYCZNY]', 'warning': ' [UWAGA]', 'unknown': ' [?]'}
    lines = [f"Terminy zewnętrzne (stan {local:%d.%m %H:%M})" + (' - UWAGA: kontrola starsza niż 48 h' if now and at and now - at > STALE else '') + ':']
    for domain in DOMAINS:
        parts = []
        for kind in ('domena', 'tls', 'dns'):
            it = by_key.get(f'{kind}:{domain}')
            if it:
                parts.append(it['detail'] + mark.get(it['level'], ''))
        lines.append(f'- {domain}: ' + '; '.join(parts))
    for key in ('saldo:openrouter', 'saldo:x', 'token:github', 'codex'):
        it = by_key.get(key)
        if it and it['level'] != 'na':
            lines.append(f"- {it['label']}: {it['detail']}{mark.get(it['level'], '')}")
    manual = [it['label'] for it in by_key.values() if it['level'] == 'manual']
    if manual:
        lines.append('- Ręcznie raz w miesiącu (brak oficjalnego API sald): ' + ', '.join(manual))
    return lines


def table(now=None):
    """Tabela tekstowa dla polecenia i skryptu wdrożenia."""
    data = snapshot()
    rows = data.get('items') or []
    if not rows:
        return 'Brak danych - uruchom: python manage.py terminy_zewnetrzne --sprawdz'
    width = max(len(it['label']) for it in rows) + 2
    out = [f"Terminy zewnętrzne, stan {data.get('checked_at', '')[:16].replace('T', ' ')}", '']
    for it in rows:
        days = '' if it.get('days') is None else f"{it['days']:>4} dni  "
        out.append(f"{it['level']:<9} {it['label']:<{width}} {days}{it['detail']}")
    return '\n'.join(out)
