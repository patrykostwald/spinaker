"""Poczta wychodząca (właściciel 7.10): kolejka listów z plików, kontrola, duplikaty z folderu Wysłane, limit, kopia, rejestr, zestawienie.
Bez sieci: IMAP i SMTP podmienione."""
from datetime import timedelta
from email import message_from_bytes, policy
from email.message import EmailMessage
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from news import poczta
from news import poczta_wychodzaca as outbox
from news.poczta_models import MailOutboxLog
from news.test_poczta import FakeSMTP

pytestmark = pytest.mark.django_db
REPO_QUEUE = Path(settings.BASE_DIR).parent / 'deploy' / 'poczta-wychodzaca'
SIGNER = 'Anna Testowa, prezes zarządu'
LETTER = ('Dzień dobry,\n\nprowadzimy spin.clinic - diagnozy chwytów retorycznych polityków tą samą miarą dla wszystkich stron. '
          'Prosimy o zgodę na pokazywanie tytułu i werdyktu Państwa weryfikacji z linkiem do źródła.\n\nZ poważaniem\nZespół spin.clinic')


class FakeIMAP:
    """Skrzynka z folderem „Sent Items” (flaga \\Sent w LIST); APPEND dopisuje do folderu, więc duplikaty widać od razu."""
    sent = {}
    appended = []
    fail = None
    folders = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "Sent Items"']

    def __init__(self, host, port, ssl_context=None):
        if FakeIMAP.fail:
            raise FakeIMAP.fail
        self.box = ''

    def login(self, user, password):
        return 'OK', [b'ok']

    def list(self):
        return 'OK', FakeIMAP.folders

    def select(self, box, readonly=False):
        self.box = box
        return ('OK', [b'1']) if box in ('"Sent Items"', 'INBOX') else ('NO', [b'missing'])

    def uid(self, command, *args):
        uids = sorted(FakeIMAP.sent)
        if command == 'search':
            return 'OK', [' '.join(str(u) for u in uids).encode()]
        raw = FakeIMAP.sent[int(args[0])]
        return 'OK', [(f'{args[0]} (BODY[] {{{len(raw)}}}'.encode(), raw), b')']

    def append(self, folder, flags, date, raw):
        FakeIMAP.appended.append((folder, raw))
        FakeIMAP.sent[max(FakeIMAP.sent, default=0) + 1] = raw
        return 'OK', [b'[APPENDUID 1 1]']

    def logout(self):
        return 'BYE', []


def sent_mail(to='kontakt@demagog.org.pl', subject='Współpraca: Państwa weryfikacje przy diagnozach spin.clinic', body='Treść.\n\n-- \nJan Testowy\nfirma sp. z o.o.'):
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'], msg['Date'] = 'kontakt@spin.clinic', to, subject, 'Mon, 05 Oct 2026 10:00:00 +0200'
    msg.set_content(body)
    return msg.as_bytes()


@pytest.fixture
def queue(monkeypatch, tmp_path):
    FakeIMAP.sent, FakeIMAP.appended, FakeIMAP.fail, FakeSMTP.sent, FakeSMTP.fail = {}, [], None, [], None
    monkeypatch.setenv('MAILBOXES', 'SPIN,IAPPLY')
    for box, address in (('SPIN', 'kontakt@spin.clinic'), ('IAPPLY', 'biuro@iapply.pl')):
        for key, value in (('IMAP_HOST', 'imap.example'), ('IMAP_USER', address), ('IMAP_PASSWORD', 'tajne'),
                           ('SMTP_HOST', 'smtp.example'), ('SMTP_USER', address), ('SMTP_PASSWORD', 'tajne'), ('LABEL', box.lower())):
            monkeypatch.setenv(poczta.env_name(box, key), value)
        monkeypatch.delenv(poczta.env_name(box, 'SIGNATURE'), raising=False)
    for name in ('MAIL_OUTBOX_SIGNER', 'MAIL_OUTBOX_DAILY_LIMIT'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('MAIL_OUTBOX_DIR', str(tmp_path))
    monkeypatch.setattr(poczta.imaplib, 'IMAP4_SSL', FakeIMAP)
    monkeypatch.setattr(poczta.smtplib, 'SMTP_SSL', FakeSMTP)
    monkeypatch.setattr(poczta.smtplib, 'SMTP', FakeSMTP)
    return tmp_path


def write(folder, key, body=LETTER, to='kontakt@demagog.org.pl', subject='Współpraca: Państwa weryfikacje przy diagnozach spin.clinic',
          mailbox='SPIN', category='partner', **extra):
    header = [f'to: {to}', f'subject: {subject}', f'mailbox: {mailbox}', f'category: {category}'] + [f'{k}: {v}' for k, v in extra.items()]
    (folder / f'{key}.md').write_text('---\n' + '\n'.join(header) + '\n---\n' + body + '\n', encoding='utf-8')
    return outbox.parse_item(folder / f'{key}.md')


def test_parse_header_and_review_rules(queue, monkeypatch):
    cfg = poczta.config('SPIN')
    item = write(queue, 'a', LETTER.replace(' - ', ' — '), attachments='brak.pdf', nieznane='x')
    assert item['to'] == 'kontakt@demagog.org.pl' and item['mailbox'] == 'SPIN' and item['lang'] == 'PL' and item['attachments'] == ['brak.pdf']
    assert '—' not in item['body'] and 'nieznane pole: nieznane' in item['problems']
    assert 'brak załącznika: brak.pdf' in outbox.check_item(item, cfg)
    clean = write(queue, 'b')
    assert outbox.check_item(clean, cfg) == []
    assert 'adres e-mail osoby trzeciej: jan@firma.pl' in outbox.check_item(write(queue, 'c', LETTER + '\nKontakt: jan@firma.pl'), cfg)
    assert outbox.check_item(write(queue, 'c2', LETTER + '\nOdpowiedź na zrodla@spin.clinic albo kontakt@demagog.org.pl'), cfg) == []
    assert any(p.startswith('oferta handlowa') for p in outbox.check_item(write(queue, 'd', LETTER + '\nOferujemy bezpłatne konta Pro.'), cfg))
    assert any(p.startswith('obietnica pieniędzy') for p in outbox.check_item(write(queue, 'e', LETTER + '\nDamy rabat.'), cfg))
    assert 'numer telefonu w treści' in outbox.check_item(write(queue, 'f', LETTER + '\nTel. 600 700 800.'), cfg)
    identifiers = write(queue, 'g', LETTER + '\nKRS 0001133291, NIP 7831915094, REGON 529962488, IP 148.113.242.109.')
    assert outbox.check_item(identifiers, cfg) == []  # dane spółki i adres IP to nie telefon ani PESEL
    assert 'ton: wykrzykniki, wersaliki albo emoji' in outbox.check_item(write(queue, 'h', LETTER + '\nPROSIMY O SZYBKĄ ODPOWIEDŹ!!!'), cfg)
    english = write(queue, 'i', 'Hello,\n\nwe run spin.clinic and would like to use OpenSanctions properly, with a licence. Kind regards,\nThe spin.clinic team', lang='EN')
    assert outbox.check_item(english, cfg) == []
    assert any(p.startswith('nie po polsku') for p in outbox.check_item(write(queue, 'j', english['body']), cfg))
    formal = write(queue, 'k', LETTER + '\n\nW imieniu iapply sp. z o.o.\n{{PODPIS}}', mailbox='IAPPLY', category='instytucja')
    assert any('MAIL_OUTBOX_SIGNER' in p for p in outbox.check_item(formal, poczta.config('IAPPLY')))
    monkeypatch.setenv('MAIL_OUTBOX_SIGNER', SIGNER)
    assert outbox.check_item(formal, poczta.config('IAPPLY')) == []
    assert any(p.startswith('miejsce do uzupełnienia') for p in outbox.check_item(write(queue, 'l', LETTER + '\n[nazwa redakcji]'), cfg))
    broken = write(queue, 'm', mailbox='INNA', category='reklama', not_before='kiedyś')
    assert len(broken['problems']) == 3
    assert outbox.extract_footer('Treść\n\n-- \nJan\nfirma') == 'Jan\nfirma'
    assert outbox.extract_footer('Treść listu.\n\nZ poważaniem\nJan Testowy\nfirma') == 'Z poważaniem\nJan Testowy\nfirma'


def test_plan_reports_everything_and_sends_nothing(queue, monkeypatch):
    write(queue, '01-dobry')
    write(queue, '02-bez-adresu', to='', contact_url='https://example.org/kontakt')
    write(queue, '03-wstrzymany', hold='po przychodach')
    future = (timezone.now() + timedelta(days=3)).date().isoformat()
    write(queue, '04-czeka', not_before=future)
    write(queue, '05-patryk', mailbox='PATRYK')
    write(queue, '06-oferta', LETTER + '\nOferujemy bezpłatny pilotaż.')
    (queue / '_README.md').write_text('opis, nie list', encoding='utf-8')
    rows = {r['key']: r for r in outbox.run(plan=True)}
    assert len(rows) == 6
    assert rows['01-dobry']['action'] == 'send'
    assert rows['02-bez-adresu'] == {**rows['02-bez-adresu'], 'action': 'skip', 'reason': 'brak adresu e-mail (adres ze strony: https://example.org/kontakt)'}
    assert rows['03-wstrzymany']['reason'] == 'wstrzymany: po przychodach'
    assert rows['04-czeka']['reason'].startswith('czeka do ')
    assert rows['05-patryk'] == {**rows['05-patryk'], 'action': 'block', 'reason': 'skrzynka PATRYK nie jest w MAILBOXES'}
    assert rows['06-oferta']['action'] == 'block' and 'PKE art. 398' in rows['06-oferta']['reason']
    assert FakeSMTP.sent == [] and FakeIMAP.appended == [] and MailOutboxLog.objects.count() == 0
    text = '\n'.join(outbox.format_rows(list(rows.values()), plan=True))
    assert 'WYŚLE' in text and 'Nic nie wysłano' in text and 'do wysłania 1, zatrzymane 2, pominięte 3' in text


def test_send_saves_copy_logs_and_skips_duplicates(queue, monkeypatch):
    write(queue, '01-demagog')
    rows = outbox.run(plan=False)
    assert rows[0]['action'] == 'sent' and len(FakeSMTP.sent) == 1 and len(FakeIMAP.appended) == 1
    sent = FakeSMTP.sent[0]
    assert sent['To'] == 'kontakt@demagog.org.pl' and sent['From'] == 'kontakt@spin.clinic' and sent['Message-ID'].endswith('@spin.clinic>')
    content = sent.get_content()
    assert LETTER in content and '-- \nspin.clinic · iapply sp. z o.o.' in content and 'KRS 0001133291' in content and 'kontakt@spin.clinic · https://spin.clinic' in content
    assert FakeIMAP.appended[0][0] == '"Sent Items"' and b'Subject:' in FakeIMAP.appended[0][1]
    log = MailOutboxLog.objects.get()
    assert log.status == 'sent' and log.key == '01-demagog' and log.copy_saved and log.message_id == sent['Message-ID'] and log.sent_at
    # drugi przebieg: rejestr blokuje ponowną wysyłkę
    assert outbox.run(plan=False)[0]['reason'].startswith('już wysłane') and len(FakeSMTP.sent) == 1
    # inny plik, ten sam adresat i podobny temat: folder Wysłane (kopia z APPEND) -> duplikat, wpis w rejestrze raz
    write(queue, '02-demagog-znow', subject='Re: Współpraca - Państwa weryfikacje przy diagnozach spin.clinic')
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['02-demagog-znow']['action'] == 'skip' and rows['02-demagog-znow']['reason'].startswith('już w Wysłane')
    outbox.run(plan=False)
    assert MailOutboxLog.objects.filter(key='02-demagog-znow', status='duplicate').count() == 1 and len(FakeSMTP.sent) == 1
    # limit dzienny: jedna wysyłka już była
    monkeypatch.setenv('MAIL_OUTBOX_DAILY_LIMIT', '1')
    write(queue, '03-inny', to='redakcja@oko.press', subject='Zestawienia dla redakcji')
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['03-inny']['reason'] == 'limit dzienny 1 na skrzynkę' and len(FakeSMTP.sent) == 1
    monkeypatch.setenv('MAIL_OUTBOX_DAILY_LIMIT', '10')
    # bez dostępu do folderu Wysłane nie wysyłamy
    FakeIMAP.fail = OSError('imap down tajne')
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['03-inny']['action'] == 'block' and rows['03-inny']['reason'] == 'bez kontroli duplikatów nie wysyłam (IMAP: OSError)'
    FakeIMAP.fail = None
    FakeSMTP.fail = OSError('smtp down')
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['03-inny']['action'] == 'failed' and MailOutboxLog.objects.filter(key='03-inny', status='failed').exists()


def test_reply_in_thread_signer_and_iapply_signature(queue, monkeypatch):
    write(queue, '05-licencja', 'Hello,\n\nwe run spin.clinic and would like to use OpenSanctions with a licence. Kind regards,\nThe spin.clinic team',
          to='info@opensanctions.org', subject='Licence enquiry: spin.clinic', lang='EN')
    # odpowiedź w wątku stoi w kolejce przed rodzicem: w pierwszym przebiegu czeka, w drugim idzie z In-Reply-To
    write(queue, '04-partnerstwo', 'Hello,\n\nwe would like to contribute Polish PEP sources from official registers. Kind regards,\nThe spin.clinic team',
          to='info@opensanctions.org', subject='Partnership proposal: Polish PEP data', lang='EN', reply_to_item='05-licencja')
    write(queue, '03-kprm', LETTER + '\n\nW imieniu iapply sp. z o.o.\n{{PODPIS}}', to='bip@kprm.gov.pl', subject='Wniosek o ponowne wykorzystywanie',
          mailbox='IAPPLY', category='instytucja')
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['05-licencja']['action'] == 'sent'
    assert rows['04-partnerstwo']['action'] == 'block' and rows['04-partnerstwo']['reason'] == 'w wątku listu 05-licencja, który jeszcze nie wyszedł'
    assert rows['03-kprm']['action'] == 'block' and 'MAIL_OUTBOX_SIGNER' in rows['03-kprm']['reason']
    first = FakeSMTP.sent[0]
    assert 'operator of spin.clinic' in first.get_content() and 'VAT PL7831915094' in first.get_content()
    monkeypatch.setenv('MAIL_OUTBOX_SIGNER', SIGNER)
    rows = {r['key']: r for r in outbox.run(plan=False)}
    assert rows['04-partnerstwo']['action'] == 'sent' and rows['03-kprm']['action'] == 'sent'
    reply = next(m for m in FakeSMTP.sent if m['Subject'].startswith('Re: Partnership'))
    assert reply['In-Reply-To'] == first['Message-ID'] and reply['References'] == first['Message-ID']
    formal = next(m for m in FakeSMTP.sent if m['From'] == 'biuro@iapply.pl')
    body = formal.get_content()
    assert SIGNER in body and '{{PODPIS}}' not in body and 'VIII Wydział Gospodarczy KRS' in body and 'kapitał zakładowy 50 000 zł' in body
    assert 'biuro@iapply.pl · https://iapply.pl' in body and 'tajne' not in body
    monkeypatch.setenv('MAILBOX_SPIN_SIGNATURE', 'Zespół spin.clinic\\nkontakt@spin.clinic')
    assert outbox.signature(poczta.config('SPIN')) == '\n\n-- \nZespół spin.clinic\nkontakt@spin.clinic'


def test_digest_lists_outbox_entries_once(queue, monkeypatch):
    write(queue, '01-demagog')
    outbox.run(plan=False)
    sent = []
    monkeypatch.setattr('news.social_publish._mail', lambda to, subject, body, **kw: sent.append((to, subject, body)) or True)
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'wlasciciel@example.com')
    out = poczta.digest()
    assert out['status'] == 'ok' and out['outbox'] == 1 and out['items'] == 0
    to, subject, body = sent[0]
    assert '1 wysyłek z kolejki' in subject and 'Poczta wychodząca' in body and 'kontakt@demagog.org.pl' in body and 'wysłano' in body
    assert 'brak wiadomości przychodzących do decyzji' in body
    assert MailOutboxLog.objects.get().digest_sent_at and poczta.digest()['status'] == 'idle'


def test_commands_plan_and_footer(queue, capsys):
    write(queue, '01-demagog')
    call_command('poczta', '--wyslij-kolejke', '--plan')
    out = capsys.readouterr().out
    assert 'WYŚLE   [SPIN] 01-demagog -> kontakt@demagog.org.pl' in out and 'Nic nie wysłano' in out and 'MAIL_OUTBOX_SIGNER): brak' in out
    assert FakeSMTP.sent == [] and MailOutboxLog.objects.count() == 0
    FakeIMAP.sent = {1: sent_mail(subject='Stary'), 2: sent_mail(subject='Najnowszy')}
    call_command('poczta', '--podpis', 'spin')
    out = capsys.readouterr().out
    assert 'Folder: Sent Items · ostatnia wiadomość: Najnowszy' in out and '   Jan Testowy\n   firma sp. z o.o.' in out
    assert 'MAILBOX_SPIN_SIGNATURE' in out and 'tajne' not in out
    call_command('poczta', '--podpis', 'PATRYK')
    assert 'nie jest w MAILBOXES' in capsys.readouterr().out
    FakeIMAP.sent = {}
    assert outbox.footer_from_sent(poczta.config('SPIN'))['note'] == 'folder Wysłane jest pusty'


def test_repo_queue_files_are_valid_and_addresses_only_from_sources(queue, monkeypatch):
    items = outbox.load_items(REPO_QUEUE)
    assert len(items) >= 27 and len({i['key'] for i in items}) == len(items)
    monkeypatch.setenv('MAIL_OUTBOX_SIGNER', SIGNER)
    with_address = {}
    for item in items:
        assert item['problems'] == [], (item['key'], item['problems'])
        assert item['mailbox'] in ('SPIN', 'IAPPLY') and '—' not in item['body'] and '–' not in item['body']
        assert item['to'] or item['contact_url'], item['key']
        if item['to']:
            with_address[item['key']] = item['to']
            assert item['source'], item['key']  # adres zawsze ze wskazanym źródłem, nigdy zgadywany
            if not item['hold']:
                assert outbox.check_item(item, poczta.config(item['mailbox'])) == [], item['key']
    assert with_address == {'03-kprm-wniosek-dane': 'bip@kprm.gov.pl', '04-rcl-wniosek-dane': 'kancelaria@rcl.gov.pl',
                            '06-demagog-zgoda': 'kontakt@demagog.org.pl', '11-konkret24-zgoda': 'kontakt24@tvn.pl',
                            '18-oko-press-zestawienia': 'redakcja@oko.press'}
    held = {i['key'] for i in items if i['hold']}
    assert {'14-frontstory-pilotaz', '18-oko-press-zestawienia', '23-redakcje-lokalne-pilotaz', '24-pap-licencja', '25-brand24-api',
            '26-sondaze-licencja', '01-sejm-wniosek-dane', '02-senat-wniosek-dane', '08-watchdog-konsultacja', '90-partner-badawczy-meta-tiktok'} <= held
    by_key = {i['key']: i for i in items}
    assert by_key['12-opensanctions-partnerstwo']['reply_to_item'] == '05-opensanctions-licencja' and by_key['12-opensanctions-partnerstwo']['lang'] == 'EN'
    assert '{{PODPIS}}' in by_key['03-kprm-wniosek-dane']['body'] and by_key['03-kprm-wniosek-dane']['mailbox'] == 'IAPPLY'
    # plan na prawdziwej kolejce: tylko adresaci z adresem i bez wstrzymania są „do wysłania”
    monkeypatch.setenv('MAIL_OUTBOX_DIR', str(REPO_QUEUE))
    rows = {r['key']: r['action'] for r in outbox.run(plan=True)}
    assert {k for k, a in rows.items() if a == 'send'} == {'03-kprm-wniosek-dane', '04-rcl-wniosek-dane', '06-demagog-zgoda', '11-konkret24-zgoda'}
    assert FakeSMTP.sent == [] and MailOutboxLog.objects.count() == 0


def test_sent_folder_detection_and_similarity():
    assert outbox._folder_name(b'(\\HasNoChildren \\Sent) "/" "Sent Items"') == ('\\HasNoChildren \\Sent', 'Sent Items')
    assert outbox._folder_name(b'(\\HasNoChildren) "." INBOX.Wyslane') == ('\\HasNoChildren', 'INBOX.Wyslane')
    assert outbox.similar('Wniosek o dane - petycje', 'Re: Wniosek o dane - petycje i druki')
    assert not outbox.similar('Współpraca: weryfikacje', 'Licencja na cytaty PAP')
    header = message_from_bytes(sent_mail(), policy=policy.default)
    assert header['Subject'].startswith('Współpraca')
