"""Raport powiązań z rejestrów urzędowych: bez modelu AI, bez sieci, bez zapisu do bazy (decyzja właściciela 7.11: szukanie za darmo).

Zasada: łączymy WYŁĄCZNIE po numerze (NIP, KRS), nigdy po nazwie. Źródło wpisów: rejestr lobbingu MSWiA (rekordy `lobby_entity`
w PublicRecord, tekst wpisu z PDF). Osoba pojawia się w raporcie tylko wtedy, gdy ma w bazie relację z podmiotem z KRS
(PublicFigureOrganisationRelation), a numer tego podmiotu występuje we wpisie rejestru. Raport nie ocenia i nie wyjaśnia powiązania.
"""
import re

from news.przeszlosc_podmiot_nip import valid_nip
from news.political_models import PublicFigureOrganisationRelation, RegisteredOrganisation
from news.public_records_models import PublicRecord

TEN_DIGITS = re.compile(r'(?<![\d-])(\d(?:[\s-]{0,3}\d){9})(?![\d])')
KRS_RE = re.compile(r'KRS\D{0,12}(\d(?:[\s-]{0,2}\d){9})(?!\d)', re.I)


def identifiers(text):
    """NIP: każdy ciąg 10 cyfr (dowolne spacje/myślniki) z poprawną sumą kontrolną; KRS: tylko po słowie KRS."""
    nips = set()
    for m in TEN_DIGITS.findall(text or ''):
        nip = valid_nip(re.sub(r'\D', '', m))
        if nip:
            nips.add(nip)
    return nips, {re.sub(r'\D', '', k) for k in KRS_RE.findall(text or '')}


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


def diagnosis(samples=3, width=220):
    """Ile wpisów zawiera słowa NIP/KRS/REGON i czy rozpoznajemy z nich numery; kilka skróconych próbek (rejestr jest publiczny)."""
    counts = {'entries': 0, 'word_nip': 0, 'word_krs': 0, 'word_regon': 0, 'nip_ok': 0, 'krs_ok': 0, 'word_but_no_number': 0}
    odd, plain = [], []
    for record in PublicRecord.objects.filter(kind='lobby_entity').only('external_id', 'text').iterator():
        text = record.text or ''
        counts['entries'] += 1
        has_nip, has_krs, has_regon = bool(re.search(r'\bNIP\b', text, re.I)), bool(re.search(r'\bKRS\b', text, re.I)), bool(re.search(r'REGON', text, re.I))
        counts['word_nip'] += has_nip
        counts['word_krs'] += has_krs
        counts['word_regon'] += has_regon
        nips, krs = identifiers(text)
        counts['nip_ok'] += bool(nips)
        counts['krs_ok'] += bool(krs)
        if (has_nip or has_krs) and not (nips or krs):
            counts['word_but_no_number'] += 1
            if len(odd) < samples:
                odd.append((record.external_id, ' '.join(text.split())[:width]))
        elif not (has_nip or has_krs) and len(plain) < samples:
            plain.append((record.external_id, ' '.join(text.split())[:width]))
    return {'counts': counts, 'word_but_no_number': odd, 'no_words': plain}
