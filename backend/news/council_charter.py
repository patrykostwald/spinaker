"""Wersjonowanie Karty i publiczna lista członków bez wywołań modeli."""
import hashlib
import re
from pathlib import Path

from news import council_registry as registry


def charter():
    text = (Path(__file__).resolve().parent / 'KARTA_KONSYLIUM.md').read_text(encoding='utf-8')
    version = re.search(r'^Wersja\s+(\S+)', text, re.M)[1]
    return text, version, hashlib.sha256(text.encode()).hexdigest()


def roster():
    from news import clinic_council as council
    members = {}
    for setting, default, role in (
        ('CLINIC_COUNCIL', council.DEFAULT_COUNCIL, 'członek'),
        ('CLINIC_COUNCIL_CHAIR', council.CHAIR, 'przewodniczący'),
        ('CLINIC_COUNCIL_LINGUIST', council.LINGUIST, 'językoznawca'),
        ('CLINIC_COUNCIL_REVIEWER', council.REVIEWER, 'recenzent'),
    ):
        for member in council._members(setting, default):
            row = members.setdefault(member, {**registry.metadata(member), 'roles': []})
            row['roles'].append(role)
            # skład stały; dzienny limit darmowego dostępu to przerwa do północy, a nie wyjście z Konsylium
            row['status'] = ('dostępny' if registry.available(member) else
                             'limit dzienny' if registry.configured(member) else 'niedostępny')
    from news.clinic_models import CouncilSeat
    try:
        for seat in CouncilSeat.objects.filter(status='suspended'):
            member = (seat.provider, seat.model)
            row = members.setdefault(member, {**registry.metadata(member), 'roles': []})
            row['status'] = 'zawieszony'
            row['suspended_reason'] = seat.last_error
    except Exception:
        pass
    return list(members.values())


def council_data():
    from news.clinic_models import CouncilCharterAcceptance
    _, version, digest = charter()
    latest = {}
    for acceptance in CouncilCharterAcceptance.objects.filter(charter_version=version, charter_hash=digest).order_by('-created_at', '-pk'):
        latest.setdefault((acceptance.provider, acceptance.model), acceptance)
    members = roster()
    for row in members:
        acceptance = latest.get((row['provider'], row['model']))
        row['charter'] = ({'version': version, 'date': acceptance.created_at,
                           **acceptance.response} if acceptance else None)
    return {'charter_version': version, 'charter_hash': digest, 'members': members, 'recruitment': recruitment_log()}


def recruitment_log(limit: int = 20) -> list[dict]:
    """Jawny dziennik Rekrutera: kandydaci z wynikiem egzaminu i głosami, zawieszenia i powroty (bez odpowiedzi na wpisy)."""
    from news.clinic_models import CouncilRecruitment
    rows = []
    for row in CouncilRecruitment.objects.all()[:limit]:
        exam = row.exam or {}
        rows.append({'date': row.created_at, 'kind': row.kind, 'model': row.model, 'company': row.company, 'provider': row.provider,
                     'decision': row.decision, 'mode': row.mode, 'roles': row.roles, 'reason': row.reason,
                     'exam': {k: exam.get(k) for k in ('items', 'answered', 'agreement', 'mae', 'passed')} if exam else None,
                     'votes': [{'model': v.get('model'), 'admit': v.get('admit'), 'reason': v.get('reason')} for v in row.votes or []]})
    return rows
