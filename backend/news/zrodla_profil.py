"""Profil osoby: bloki z nowych otwartych źródeł (raport źródeł 6.10). Tylko baza, bez sieci.

Osoba = oficjalny identyfikator (poseł X kadencji albo europoseł po id PE) albo powiązanie już zapisane w rekordzie;
nigdy samo nazwisko. Przy każdym bloku: źródło, licencja i data. Wskazówki kont X z Wikidata nie są pokazywane
(nie są potwierdzone; zasada podwójnego potwierdzenia zostaje).
"""
from django.db.models import F, Q

POSITION = {'FOR': 'za', 'AGAINST': 'przeciw', 'ABSTENTION': 'wstrzymał(a) się', 'DID_NOT_VOTE': 'nie głosował(a)'}


def ep_ids(figure):
    from scraper.public_records import EP_TERM  # noqa: F401
    ids = set()
    entry = figure.parliamentary_roster_entry
    if entry and entry.source == 'ep' and str(entry.external_id).isdigit():
        ids.add(int(entry.external_id))
    for key in figure.public_roles.filter(import_key__startswith='ep:').values_list('import_key', flat=True):
        tail = key.split(':', 1)[1]
        if tail.isdigit():
            ids.add(int(tail))
    return ids


def records(figure, identities, source, kinds):
    from news.public_records_models import PublicRecord
    from scraper.public_records import EP_TERM
    q = Q(people__figure=figure)
    for term, mp_id in identities:
        q |= Q(people__term=term, people__mp_id=mp_id)
    for ep in ep_ids(figure):
        q |= Q(people__term=EP_TERM, people__mp_id=ep)
    return (PublicRecord.objects.filter(q, source=source, kind__in=kinds).distinct()
            .order_by(F('date').desc(nulls_last=True), '-pk'))


def _ep_vote(record, ids):
    data = record.data or {}
    mine = next((v for v in data.get('votes') or [] if v.get('ep_id') in ids), None)
    return {'date': record.date.isoformat() if record.date else None, 'title': record.title[:300],
            'reference': data.get('reference', ''), 'position': POSITION.get((mine or {}).get('position'), ''),
            'polish': {POSITION.get(k, k): n for k, n in (data.get('polish') or {}).items()}, 'url': record.source_url}


def open_data(figure, identities):
    from scraper.nowe_zrodla import LICENSES
    out, used = {}, set()
    ids = ep_ids(figure)
    votes = records(figure, identities, 'howtheyvote', ['ep_vote'])
    if votes.exists():
        own = set(ids)
        if not own:  # europoseł połączony przez rekord (id PE z rekordu, który już wskazuje tę osobę)
            from news.public_records_models import PublicRecordPerson
            from scraper.public_records import EP_TERM
            own = set(PublicRecordPerson.objects.filter(figure=figure, term=EP_TERM).values_list('mp_id', flat=True))
        rows = [_ep_vote(r, own) for r in votes[:20]]
        out['ep_votes'] = {'count': votes.count(), 'results': rows}
        used.add('howtheyvote')
    mep = records(figure, identities, 'integrity_watch', ['mep']).first()
    income = records(figure, identities, 'integrity_watch', ['mep_income']).first()
    meetings = records(figure, identities, 'integrity_watch', ['mep_meeting'])
    if mep or income or meetings.exists():
        out['ep_integrity'] = {
            'declarations': (mep.data.get('declarations') if mep else []) or [],
            'income': {'total_eur': income.data.get('total_eur'), 'paid': income.data.get('paid_activities'),
                       'activities': [a for a in income.data.get('activities') or [] if a.get('total_eur')][:12]} if income else None,
            'meetings': {'count': meetings.count(), 'results': [
                {'date': m.date.isoformat() if m.date else None, 'lobbyists': m.data.get('lobbyists', ''),
                 'title': m.data.get('title', ''), 'role': m.data.get('role', '')} for m in meetings[:15]]},
        }
        used.add('integrity_watch')
    person = records(figure, identities, 'wikidata', ['person']).first()
    if person:
        data = person.data or {}
        out['identity'] = {'wikidata': person.source_url, 'wikipedia': data.get('wikipedia', ''),
                           'parties': data.get('parties') or [], 'sejm_ids': data.get('sejm_ids') or [],
                           'ep_ids': data.get('ep_ids') or []}
        used.add('wikidata')
    mileage = records(figure, identities, 'mileage', ['mileage'])
    offices = records(figure, identities, 'mileage', ['office_report'])
    if mileage.exists() or offices.exists():
        out['mp_expenses'] = {
            'mileage': [{'period': m.data.get('period'), 'amount_pln': m.data.get('amount_pln'), 'km': m.data.get('km'),
                         'check': m.data.get('check'), 'origin': m.data.get('origin'), 'origin_url': m.data.get('origin_url')}
                        for m in mileage[:6]],
            'offices': [{'year': o.data.get('year'), 'total_pln': o.data.get('total_pln'), 'pdf_url': o.data.get('pdf_url'),
                         'check': o.data.get('pdf_check'), 'items': (o.data.get('items') or [])[:23]} for o in offices[:4]],
        }
        used.add('mileage')
    out['sources'] = [{'key': k, **LICENSES[k]} for k in sorted(used)]
    return out
