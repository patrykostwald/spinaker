"""Raport powiązań z rejestrów urzędowych: bez modelu AI, bez sieci, bez zapisu do bazy (decyzja właściciela 7.11: szukanie za darmo).

Zasada: łączymy WYŁĄCZNIE po numerze (NIP, KRS), nigdy po nazwie. Źródło wpisów: rejestr lobbingu MSWiA (rekordy `lobby_entity`
w PublicRecord, tekst wpisu z PDF). Osoba pojawia się w raporcie tylko wtedy, gdy ma w bazie relację z podmiotem z KRS
(PublicFigureOrganisationRelation), a numer tego podmiotu występuje we wpisie rejestru. Raport nie ocenia i nie wyjaśnia powiązania.
"""
import re

from news.political_models import PublicFigureOrganisationRelation, RegisteredOrganisation
from news.public_records_models import PublicRecord

NIP_RE = re.compile(r'NIP\D{0,12}(\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\d{3}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{3})', re.I)
KRS_RE = re.compile(r'KRS\D{0,12}(\d{10})\b', re.I)


def identifiers(text):
    nips = {re.sub(r'\D', '', m) for m in NIP_RE.findall(text or '')}
    return {n for n in nips if len(n) == 10}, set(KRS_RE.findall(text or ''))


def lobbying_report(limit=200):
    """Zwraca {'entries', 'with_ids', 'matched_orgs', 'rows'}; rows: osoba, podmiot, rola, numer wpisu w rejestrze lobbingu."""
    orgs_by_nip, orgs_by_krs = {}, {}
    for org in RegisteredOrganisation.objects.filter(archived=False).exclude(nip='').only('id', 'name', 'krs_number', 'nip'):
        orgs_by_nip.setdefault(org.nip, org)
    for org in RegisteredOrganisation.objects.filter(archived=False).only('id', 'name', 'krs_number', 'nip'):
        orgs_by_krs[org.krs_number] = org
    entries = with_ids = 0
    matched = {}
    for record in PublicRecord.objects.filter(kind='lobby_entity').only('external_id', 'text', 'source_url').iterator():
        entries += 1
        nips, krs = identifiers(record.text)
        if not nips and not krs:
            continue
        with_ids += 1
        found = {orgs_by_krs[k].pk: orgs_by_krs[k] for k in krs if k in orgs_by_krs}
        found.update({orgs_by_nip[n].pk: orgs_by_nip[n] for n in nips if n in orgs_by_nip})
        for org in found.values():
            matched.setdefault(org.pk, (org, record))
    rows = []
    relations = (PublicFigureOrganisationRelation.objects.filter(organisation_id__in=list(matched))
                 .select_related('public_figure', 'organisation').order_by('public_figure__canonical_name'))
    for rel in relations[:limit]:
        org, record = matched[rel.organisation_id]
        rows.append({'figure_id': rel.public_figure_id, 'figure': rel.public_figure.canonical_name, 'organisation': org.name,
                     'krs': org.krs_number, 'role': rel.public_role, 'organ': rel.organ, 'status': rel.relation_status,
                     'verification': rel.verification_status, 'lobby_entry': record.external_id, 'source': record.source_url})
    return {'entries': entries, 'with_ids': with_ids, 'matched_orgs': len(matched), 'rows': rows}
