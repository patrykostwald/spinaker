"""Odczyt uchwał PKW o sprawozdaniach partii (parsers.pkw_report, kind pkw_pdf w zbieraczu): tylko tekst, bez OCR i bez danych osób."""
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from news.public_records_models import PublicCollectionState, PublicRecord
from scraper import public_record_parsers as parsers
from scraper.public_records import handle

PIRATES = """UCHWAŁA NR 272/2025 PAŃSTWOWEJ KOMISJI WYBORCZEJ z dnia 14 listopada 2025 r.
w sprawie sprawozdania partii politycznej Polska Partia Piratów o źródłach pozyskania środków finansowych w 2024 r.
Państwowa Komisja Wyborcza, na podstawie art. 38a ust. 1 pkt 2 ustawy z dnia 27 czerwca 1997 r. o partiach politycznych,
**postanawia**
**przyjąć** sprawozdanie partii politycznej Polska Partia Piratów o źródłach pozyskania środków finansowych w 2024 r. **ze wskazaniem uchybienia** polegającego na niewprowadzeniu do umowy rachunku bankowego zastrzeżenia.
## Uzasadnienie
Partia wykazała, że w okresie sprawozdawczym pozyskała przychody o łącznej wartości 4138,33 zł. Na rachunki bankowe, w tym o nr 13 2030 0045 1110 0000 0260 5970, wpłynęły środki pochodzące od osób fizycznych w kwocie 940,00 zł, na które złożyły się: -składki członkowskie w kwocie nieprzekraczającej w jednym roku wysokości minimalnego wynagrodzenia za pracę: 720,00 zł; -darowizny (pieniężne): 220,00 zł. Ponadto Partia wskazała, że przyjęła wartości niepieniężne w postaci usług, wycenione na kwotę 3198,33 zł. Stan środków na rachunku tego Funduszu w dniu 1 stycznia 2024 r. wynosił 0,00 zł. W okresie sprawozdawczym na rachunek Funduszu Wyborczego Partii wpłynęły środki w kwocie 900,80 zł, pochodzące z wpłat własnych Partii.
Przewodniczący Państwowej Komisji Wyborczej Sylwester Marciniak (dokument podpisany elektronicznie)"""


def test_resolution_text_is_parsed_into_decision_year_and_amounts_without_account_numbers():
    r = parsers.pkw_report(PIRATES)
    assert r['resolution'] == '272/2025' and r['resolution_date'] == '2025-11-14' and r['subject_kind'] == 'partia'
    assert r['name'] == 'Polska Partia Piratów' and r['report_year'] == 2024
    assert r['decision'] == 'przyjete' and r['with_irregularity'] is True
    assert {k: Decimal(v) for k, v in r['amounts'].items()} == {
        'income_total': Decimal('4138.33'), 'individuals_total': Decimal('940.00'), 'membership_fees': Decimal('720.00'),
        'donations_cash': Decimal('220.00'), 'non_cash_value': Decimal('3198.33'), 'election_fund_inflow': Decimal('900.80')}
    assert 'przychody o łącznej wartości 4138,33 zł' in r['evidence']['income_total']
    assert '2030 0045' not in str(r) and 'Marciniak' not in str(r)   # bez numerów rachunków i nazwisk


def test_rejection_and_clean_acceptance_and_non_resolutions():
    rejected = PIRATES.replace('**przyjąć**', '**odrzucić**')
    assert parsers.pkw_report(rejected)['decision'] == 'odrzucone' and parsers.pkw_report(rejected)['with_irregularity'] is False
    clean = parsers.pkw_report(PIRATES.replace('**ze wskazaniem uchybienia**', ''))
    assert clean['decision'] == 'przyjete' and clean['with_irregularity'] is False
    assert parsers.pkw_report('Sprawozdanie finansowe o przychodach, wydatkach i zobowiązaniach finansowych komitetu wyborczego 1. Pełna nazwa') is None
    assert parsers.pkw_report('') is None and parsers.pkw_report(None) is None
    thousands = parsers.pkw_report(PIRATES.replace('4138,33 zł', '1 234 567,89 zł'))
    assert Decimal(thousands['amounts']['income_total']) == Decimal('1234567.89')    # separator tysięcy: spacja


@pytest.fixture
def job(db):
    state, _ = PublicCollectionState.objects.get_or_create(source='pkw')
    return SimpleNamespace(kind='pkw_pdf', state=state, state_id=state.pk, url='https://pkw.gov.pl/uploaded_files/1763540629_ewp-328-polska-partia-piratow.pdf',
                           context={}, pk=1)


def test_collector_stores_readable_report_under_the_document_key(job):
    raw = b'%PDF-1.4 fake'
    with patch('scraper.public_records.parsers.pdf_text', return_value=PIRATES * 2):
        handle(job, raw)
    rec = PublicRecord.objects.get(source='pkw', kind='financial_report')
    assert rec.external_id == sha256(job.url.encode()).hexdigest() and rec.data['readable'] is True and rec.date.isoformat() == '2025-11-14'
    assert rec.title == 'Polska Partia Piratów (2024)' and rec.data['amounts']['income_total'] == '4138.33'


def test_scan_without_text_layer_is_recorded_as_unreadable_without_ocr(job):
    with patch('scraper.public_records.parsers.pdf_text', return_value='  \n '):
        handle(job, b'%PDF-1.4 scan')
    data = PublicRecord.objects.get(source='pkw', kind='financial_report').data
    assert data['readable'] is False and data['reason'] == 'skan_bez_warstwy_tekstowej' and 'amounts' not in data
    with patch('scraper.public_records.parsers.pdf_text', side_effect=ValueError('invalid_or_large_pdf')):
        handle(job, b'%PDF-1.4 big')
    assert PublicRecord.objects.get(source='pkw', kind='financial_report').data['reason'] == 'invalid_or_large_pdf'


def test_seed_command_counts_then_enqueues_only_missing_pdfs(db):
    from io import StringIO
    from django.core.management import call_command
    from news.public_records_models import PublicCollectionJob
    for i, url in enumerate(['https://pkw.gov.pl/uploaded_files/1_a.pdf', 'https://pkw.gov.pl/uploaded_files/2_b.pdf', 'https://pkw.gov.pl/finansowanie-polityki/x.html']):
        PublicRecord.objects.create(source='pkw', kind='financial_document', external_id=f'd{i}', source_url=url, response_url=url, response_sha256='0')
    PublicRecord.objects.create(source='pkw', kind='financial_report', external_id='r', source_url='https://pkw.gov.pl/uploaded_files/1_a.pdf',
                                response_url='https://pkw.gov.pl/uploaded_files/1_a.pdf', response_sha256='0', data={'readable': True})
    out = StringIO(); call_command('pkw_raporty_zasiej', stdout=out)
    assert 'PDF-ów w spisie: 2, już odczytanych: 1, do odczytu: 1' in out.getvalue() and PublicCollectionJob.objects.count() == 0
    call_command('pkw_raporty_zasiej', '--apply', stdout=StringIO()); call_command('pkw_raporty_zasiej', '--apply', stdout=StringIO())
    assert list(PublicCollectionJob.objects.values_list('kind', flat=True)) == ['pkw_pdf']
