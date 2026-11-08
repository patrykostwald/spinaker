"""Domeny urzędowe i partyjne do ścieżki osoby w zgłoszeniach par (decyzja właściciela 13.10).

Lista bazowa: plik `news/config/official_domains.json` (każda pozycja ze źródłem, datą sprawdzenia i statusem
„potwierdzona” albo „do potwierdzenia” - obie działają od razu). Env `POSITION_PAIR_OFFICIAL_DOMAINS` (lista po przecinku),
gdy ustawiona, zastępuje plik. Zmiany w działaniu: komenda `domeny_urzedowe dodaj|usun` (dziennik OfficialDomainChange;
ostatni wpis dla domeny wygrywa). Dopasowanie po sufiksie domeny, bez wielkości liter (sejm.gov.pl obejmuje poddomeny).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

CONFIG = Path(__file__).resolve().parent / 'config' / 'official_domains.json'
DOMAIN = re.compile(r'^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')
EMAIL = re.compile(r'^[^@\s]+@([^@\s]+)$')


def _host(value) -> str:
    """Host bez schematu, ścieżki, portu i kropki na końcu; IDN do punycode (IDNA), małe litery."""
    host = re.sub(r'^[a-z]+://', '', str(value or '').strip().lower())
    host = host.split('/')[0].split('?')[0].split(':')[0].rstrip('.')
    if host.startswith('www.'):
        host = host[4:]
    try:
        return host.encode('idna').decode('ascii') if host else ''
    except UnicodeError:
        return ''


def normalize(domain) -> str:
    host = _host(domain)
    if not DOMAIN.match(host):
        raise ValueError(f'Niepoprawna domena: {str(domain)!r}')
    return host


def file_entries() -> list[dict]:
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    return [{**row, 'domain': normalize(row['domain']), 'origin': 'plik'} for row in data.get('domains', [])
            if str(row.get('domain', '')).strip()]


def entries() -> list[dict]:
    """Obowiązująca lista z pochodzeniem: env (gdy ustawiony) albo plik, potem zmiany z dziennika w bazie."""
    env = []
    for value in getattr(settings, 'POSITION_PAIR_OFFICIAL_DOMAINS', []) or []:
        try:
            env.append(normalize(value))
        except ValueError:
            continue  # puste i niepoprawne wpisy w env pomijamy
    if env:
        base = {d: {'domain': d, 'kind': '', 'label': '', 'status': 'z env', 'source': 'env', 'checked': '', 'origin': 'env'}
                for d in env}
    else:
        base = {row['domain']: row for row in file_entries()}
    try:
        from news.clinic_models import OfficialDomainChange
        latest = {}
        for change in OfficialDomainChange.objects.order_by('changed_at', 'pk'):
            latest[change.domain] = change
    except Exception:  # noqa: BLE001 - brak tabeli (przed migracją) nie wyłącza listy z pliku
        latest = {}
    for domain, change in latest.items():
        if change.action == 'remove':
            base.pop(domain, None)
        else:
            base[domain] = {'domain': domain, 'kind': change.kind, 'label': change.note, 'status': 'dodana komendą',
                            'source': change.source, 'checked': change.changed_at.date().isoformat(), 'origin': 'baza'}
    return sorted(base.values(), key=lambda row: row['domain'])


def domains() -> list[str]:
    return [row['domain'] for row in entries()]


def match(email_or_domain) -> str | None:
    """Domena z listy, do której pasuje adres (po sufiksie, bez wielkości liter) albo None."""
    value = str(email_or_domain or '').strip().lower()
    found = EMAIL.match(value)
    host = _host(found.group(1) if found else value)
    if not host:
        return None
    for domain in domains():
        if host == domain or host.endswith('.' + domain):
            return domain
    return None


def change(domain, action, *, kind='', source='', note='', by=''):
    from news.clinic_models import OfficialDomainChange
    return OfficialDomainChange.objects.create(domain=normalize(domain), action=action, kind=kind[:16], source=source[:500],
                                               note=note[:300], changed_by=str(by)[:150])


def check(domain) -> dict:
    """Czy domena istnieje w DNS (A/AAAA) i ma rekord MX (gdy jest dnspython). Bez wysyłania wiadomości."""
    import socket
    result = {'domain': domain, 'dns': False, 'mx': None}
    try:
        socket.getaddrinfo(domain, None)
        result['dns'] = True
    except OSError:
        pass
    try:
        import dns.resolver  # type: ignore  # opcjonalne, jeśli zainstalowane; nie instalujemy
        result['mx'] = bool(list(dns.resolver.resolve(domain, 'MX')))
    except ImportError:
        result['mx'] = None  # brak biblioteki: sprawdzamy tylko DNS
    except Exception:  # noqa: BLE001
        result['mx'] = False
    return result
