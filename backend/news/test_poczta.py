"""Poczta (właściciel 6.10): skrzynki projektów czytane i obsługiwane przez agenta. Bez sieci: IMAP, SMTP i model podmienione."""
from datetime import timedelta
from email.message import EmailMessage
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.utils import timezone

from news import poczta
from news.poczta_models import MailboxState, MailMessage

pytestmark = pytest.mark.django_db
BOX = 'SPIN'


def raw_mail(sender='Jan Czytelnik <jan@example.org>', subject='Pytanie o diagnozę', body='Dzień dobry, jak liczycie natężenie spinu?',
             message_id='<m1@example.org>', html=False, **headers):
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'], msg['Message-ID'] = sender, 'kontakt@spin.clinic', subject, message_id
    msg['Date'] = 'Tue, 06 Oct 2026 10:00:00 +0200'
    for key, value in headers.items():
        msg[key.replace('_', '-')] = value
    if html:
        msg.set_content('wersja tekstowa')
        msg.add_alternative(f'<html><body><p>{body}</p><p>Drugi akapit</p></body></html>', subtype='html')
    else:
        msg.set_content(body)
    return msg.as_bytes()


class FakeIMAP:
    boxes = {}
    fail = None
    validity = b'100'

    def __init__(self, host, port, ssl_context=None):
        if FakeIMAP.fail:
            raise FakeIMAP.fail
        self.host, self.port = host, port

    def login(self, user, password):
        return 'OK', [b'ok']

    def select(self, box, readonly=False):
        return 'OK', [str(len(FakeIMAP.boxes)).encode()]

    def response(self, name):
        return name, [FakeIMAP.validity]

    def uid(self, command, *args):
        uids = sorted(FakeIMAP.boxes)
        if command == 'search':
            crit = args[-1]
            if crit.startswith('UID '):
                start = int(crit.split()[1].split(':')[0])
                found = [u for u in uids if u >= start] or uids[-1:]
            else:
                found = uids
            return 'OK', [' '.join(str(u) for u in found).encode()]
        uid = int(args[0])
        return 'OK', [(f'{uid} (BODY[] {{1}}'.encode(), FakeIMAP.boxes[uid]), b')']

    def logout(self):
        return 'BYE', []


class FakeSMTP:
    sent = []
    fail = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host

    def __enter__(self):
        if FakeSMTP.fail:
            raise FakeSMTP.fail
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        return 'OK'

    def starttls(self, context=None):
        return 'OK'

    def send_message(self, message):
        FakeSMTP.sent.append(message)


@pytest.fixture
def mailbox(monkeypatch):
    cache.clear()
    FakeIMAP.boxes, FakeIMAP.fail, FakeIMAP.validity, FakeSMTP.sent, FakeSMTP.fail = {}, None, b'100', [], None
    monkeypatch.setenv('MAILBOXES', 'spin')
    for key, value in (('IMAP_HOST', 'imap.example'), ('IMAP_USER', 'kontakt@spin.clinic'), ('IMAP_PASSWORD', 'tajne'),
                       ('SMTP_HOST', 'smtp.example'), ('SMTP_USER', 'kontakt@spin.clinic'), ('SMTP_PASSWORD', 'tajne'), ('LABEL', 'spin.clinic')):
        monkeypatch.setenv(poczta.env_name(BOX, key), value)
    monkeypatch.delenv('MAIL_AGENT_AUTOSEND', raising=False)
    monkeypatch.delenv('MAIL_AGENT_DAILY_LIMIT', raising=False)
    monkeypatch.setattr(poczta.imaplib, 'IMAP4_SSL', FakeIMAP)
    monkeypatch.setattr(poczta.smtplib, 'SMTP_SSL', FakeSMTP)
    monkeypatch.setattr(poczta.smtplib, 'SMTP', FakeSMTP)
    return poczta.config(BOX)


GOOD_REPLY = ('Dziękujemy za wiadomość. Natężenie spinu liczymy tą samą miarą dla każdej strony - opis metody jest na '
              'https://spin.clinic/metoda. Jeśli coś pozostanie niejasne, zespół odpowie w tym wątku.')


def model(category='question', confidence=90, reply=GOOD_REPLY, reason='Pytanie o metodę.'):
    def ask(data):
        return {'category': category, 'confidence': confidence, 'reason': reason, 'reply': reply}, ('inception', 'mercury')
    return ask


def test_config_from_env_names_only_and_missing(monkeypatch):
    monkeypatch.setenv('MAILBOXES', 'spin, zbudujmi')
    monkeypatch.setenv('MAILBOX_SPIN_IMAP_HOST', 'h')
    monkeypatch.setenv('MAILBOX_SPIN_IMAP_USER', 'u@spin.clinic')
    monkeypatch.setenv('MAILBOX_SPIN_IMAP_PASSWORD', 'p')
    for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'):
        monkeypatch.delenv(poczta.env_name('SPIN', key), raising=False)
    assert poczta.names() == ['SPIN', 'ZBUDUJMI']
    cfg = poczta.config('SPIN')
    assert poczta.imap_ready(cfg) and not poczta.smtp_ready(cfg) and cfg['address'] == 'u@spin.clinic' and cfg['label'] == 'spin'
    assert poczta.missing('SPIN') == ['MAILBOX_SPIN_SMTP_HOST', 'MAILBOX_SPIN_SMTP_USER', 'MAILBOX_SPIN_SMTP_PASSWORD']
    assert len(poczta.missing('ZBUDUJMI')) == 6 and not poczta.imap_ready(poczta.config('ZBUDUJMI'))
    assert poczta.enabled() and not poczta.autosend() and poczta.daily_limit() == 20
    monkeypatch.setenv('MAILBOXES', '')
    assert not poczta.enabled()


def test_parse_plain_html_and_automaton():
    plain = poczta.parse(raw_mail())
    assert plain['sender_address'] == 'jan@example.org' and plain['body'].startswith('Dzień dobry') and not plain['auto_generated']
    assert plain['received_at'] is not None and plain['thread_key'] == poczta.thread_key('jan@example.org', 'Re: Pytanie o diagnozę')
    html = poczta.parse(raw_mail(html=True))
    assert html['body'] == 'wersja tekstowa'  # tekstowa część ma pierwszeństwo
    auto = poczta.parse(raw_mail(sender='Mailer <mailer-daemon@example.org>', Auto_Submitted='auto-replied'))
    assert auto['auto_generated']
    bulk = poczta.parse(raw_mail(Precedence='bulk'))
    assert bulk['auto_generated']


def test_fetch_tracks_uid_idempotent_and_resets_on_uidvalidity(mailbox):
    FakeIMAP.boxes = {1: raw_mail(message_id='<a@x>'), 2: raw_mail(message_id='<b@x>', subject='Drugi')}
    first = poczta.fetch(mailbox)
    assert first['created'] == 2 and MailMessage.objects.count() == 2
    state = MailboxState.objects.get(mailbox=BOX)
    assert state.last_uid == 2 and state.uidvalidity == '100' and state.last_ok_at and not state.last_error
    assert poczta.fetch(mailbox)['created'] == 0  # tylko UID powyżej ostatniego (serwer zwraca ostatni mimo UID 3:*)
    FakeIMAP.boxes[3] = raw_mail(message_id='<c@x>', subject='Trzeci')
    assert poczta.fetch(mailbox)['created'] == 1 and MailboxState.objects.get(mailbox=BOX).last_uid == 3
    FakeIMAP.validity = b'200'  # nowa numeracja: od początku, duplikaty po Message-ID
    assert poczta.fetch(mailbox)['created'] == 0 and MailMessage.objects.count() == 3
    assert MailboxState.objects.get(mailbox=BOX).uidvalidity == '200'


def test_fetch_error_recorded_without_secrets(mailbox):
    FakeIMAP.fail = OSError('login failed for kontakt@spin.clinic tajne')
    with pytest.raises(poczta.MailboxError):
        poczta.fetch(mailbox)
    state = MailboxState.objects.get(mailbox=BOX)
    assert state.last_error == 'OSError' and state.consecutive_errors == 1 and 'tajne' not in state.last_error


def test_check_reply_rules(mailbox):
    assert poczta.check_reply(GOOD_REPLY, mailbox) == []
    assert 'długa kreska' in poczta.check_reply(GOOD_REPLY + ' A to — kreska.', mailbox)
    assert poczta.fix_dashes('a — b – c') == 'a - b - c'
    assert 'obietnica pieniędzy lub cen' in poczta.check_reply('Dziękujemy za wiadomość, zwrócimy pieniądze i damy rabat na stronę.', mailbox)
    assert 'stanowisko prawne' in poczta.check_reply('Dziękujemy za wiadomość. Nasze stanowisko prawne jest takie, że nie ma naruszenia.', mailbox)
    assert 'adres e-mail w treści' in poczta.check_reply('Dziękujemy za wiadomość, proszę napisać do jan.kowalski@firma.pl w tej sprawie.', mailbox)
    assert 'numer telefonu' in poczta.check_reply('Dziękujemy za wiadomość, proszę dzwonić pod 600 700 800 do zespołu.', mailbox)
    assert 'obcy link' in poczta.check_reply('Dziękujemy za wiadomość, szczegóły są na https://example.com/x dla Państwa.', mailbox)
    assert 'nie po polsku' in poczta.check_reply('Thank you for your message, our team will get back to you shortly with answers.', mailbox)
    assert 'za krótka' in poczta.check_reply('Dziękujemy.', mailbox)


def stored(**extra):
    data = poczta.parse(raw_mail(**{k: v for k, v in extra.items() if k in ('sender', 'subject', 'body', 'message_id')}))
    fields = {k: v for k, v in extra.items() if k not in ('sender', 'subject', 'body', 'message_id')}
    return MailMessage.objects.create(mailbox=BOX, uid=MailMessage.objects.count() + 1, **data, **fields)


def test_decision_matrix(mailbox, monkeypatch):
    now = timezone.now()
    spam = stored(category='spam', confidence=95)
    assert poczta.decision(spam, mailbox, now) == ('skip', 'spam')
    inst = stored(category='institution', confidence=95, reply_draft='', message_id='<i@x>')
    assert poczta.decision(inst, mailbox, now)[0] == 'escalate'
    low = stored(category='question', confidence=50, reply_draft=GOOD_REPLY, message_id='<l@x>')
    assert poczta.decision(low, mailbox, now) == ('escalate', 'pewność 50 poniżej 70')
    risk = stored(category='question', confidence=95, reply_draft=GOOD_REPLY, body='Idę z tym do sądu i do prasy.', message_id='<r@x>')
    assert poczta.decision(risk, mailbox, now) == ('escalate', 'słowo ryzyka: sądu')
    ok = stored(category='question', confidence=95, reply_draft=GOOD_REPLY, body='Sądzę, że to pozwala na pytanie o metodę.', message_id='<o@x>')
    assert poczta.decision(ok, mailbox, now) == ('escalate', 'MAIL_AGENT_AUTOSEND wyłączone (szkic do wglądu)')
    monkeypatch.setenv('MAIL_AGENT_AUTOSEND', 'true')
    assert poczta.decision(ok, mailbox, now) == ('send', '')
    assert poczta.decision(ok, mailbox, now, ['obcy link']) == ('escalate', 'kontrola szkicu: obcy link')
    ok.status, ok.reply_sent_at = 'replied', now
    ok.save()
    again = stored(category='question', confidence=95, reply_draft=GOOD_REPLY, subject='Re: Pytanie o diagnozę', message_id='<o2@x>')
    assert poczta.decision(again, mailbox, now) == ('skip', 'wątek: odpowiedź w ostatnich 24 h')
    monkeypatch.setenv('MAIL_AGENT_DAILY_LIMIT', '1')
    other = stored(category='press', confidence=95, reply_draft=GOOD_REPLY, sender='Red <red@gazeta.pl>', subject='Komentarz', message_id='<p@x>')
    assert poczta.decision(other, mailbox, now) == ('escalate', 'limit dzienny 1 odpowiedzi')
    monkeypatch.setenv('MAIL_AGENT_DAILY_LIMIT', '20')
    monkeypatch.delenv('MAILBOX_SPIN_SMTP_HOST')
    assert poczta.decision(other, poczta.config(BOX), now) == ('escalate', 'brak SMTP: MAILBOX_SPIN_SMTP_HOST')


def test_run_end_to_end_sends_threaded_reply_only_with_autosend(mailbox, monkeypatch):
    monkeypatch.setattr(poczta, 'ask', model())
    FakeIMAP.boxes = {1: raw_mail(message_id='<q@x>', References='<r0@x>'),
                      2: raw_mail(sender='Biuro <biuro@urzad.gov.pl>', subject='Wezwanie do usunięcia', body='Wzywamy do usunięcia diagnozy.', message_id='<u@x>'),
                      3: raw_mail(sender='Lista <newsletter@sklep.pl>', subject='Promocja', body='Kup teraz', message_id='<n@x>', List_Id='<l.sklep.pl>')}
    result = poczta.run()
    assert result['status'] == 'ok' and result['received'] == 3 and result['replied'] == 0 and result['escalated'] == 2 and result['skipped'] == 1
    assert FakeSMTP.sent == []  # wyłącznik domyślnie wyłączony: szkic czeka w zestawieniu
    question = MailMessage.objects.get(message_id='<q@x>')
    assert question.status == 'escalated' and 'MAIL_AGENT_AUTOSEND' in question.status_reason and question.reply_draft == GOOD_REPLY
    assert MailMessage.objects.get(message_id='<n@x>').status == 'skipped'
    assert MailMessage.objects.get(message_id='<u@x>').model_name == 'mercury'
    # właściciel włącza wysyłkę: ta sama wiadomość ponownie jako nowa
    monkeypatch.setenv('MAIL_AGENT_AUTOSEND', 'true')
    question.status, question.status_reason, question.escalated_at = 'new', '', None
    question.save()
    result = poczta.run()
    assert result['replied'] == 1 and len(FakeSMTP.sent) == 1
    sent = FakeSMTP.sent[0]
    assert sent['In-Reply-To'] == '<q@x>' and sent['References'] == '<r0@x> <q@x>' and sent['Subject'] == 'Re: Pytanie o diagnozę'
    assert sent['To'] == 'Jan Czytelnik <jan@example.org>' and sent['From'] == 'kontakt@spin.clinic' and sent['Auto-Submitted'] == 'auto-replied'
    assert GOOD_REPLY in sent.get_content() and 'automatyczny asystent' in sent.get_content()
    question.refresh_from_db()
    assert question.status == 'replied' and question.reply_sent_at and question.reply_message_id.startswith('<')
    assert poczta.counts()['replied'] == 1 and 'odpowiedziane automatycznie: 1' in poczta.report_lines()[0]


def test_smtp_failure_marks_failed_and_goes_to_digest(mailbox, monkeypatch):
    monkeypatch.setenv('MAIL_AGENT_AUTOSEND', 'true')
    FakeSMTP.fail = OSError('smtp down')
    row = stored(category='question', confidence=95, reply_draft=GOOD_REPLY, message_id='<f@x>')
    assert poczta.process(row, mailbox, timezone.now()) == 'failed'
    assert row.status_reason == 'SMTP: OSError' and row.escalated_at
    sent = []
    monkeypatch.setattr('news.social_publish._mail', lambda to, subject, body, **kw: sent.append((to, subject, body, kw)) or True)
    monkeypatch.setenv('LOOP_REPORT_EMAIL', 'wlasciciel@example.com')
    out = poczta.digest()
    assert out == {'status': 'ok', 'items': 1, 'sent': True, 'outbox': 0}
    to, subject, body, kw = sent[0]
    assert to == 'wlasciciel@example.com' and kw == {'important': True} and 'proponowany szkic' in body and 'SMTP: OSError' in body
    assert MailMessage.objects.get(pk=row.pk).digest_sent_at and poczta.digest()['status'] == 'idle'


def test_window_closed_waits_then_escalates(mailbox, monkeypatch):
    from news.agents_common import WindowClosed

    def closed(data):
        raise WindowClosed('brak modeli')
    monkeypatch.setattr(poczta, 'ask', closed)
    row = stored(message_id='<w@x>')
    now = timezone.now()
    for _ in range(poczta.MAX_CLASSIFY_ATTEMPTS - 1):
        assert poczta.process(row, mailbox, now) == 'new'
    assert poczta.process(row, mailbox, now) == 'escalated'
    row.refresh_from_db()
    assert row.category == 'other' and row.category_reason.startswith('brak wolnego modelu')


def test_retention_removes_body_after_180_days(mailbox):
    old = stored(message_id='<old@x>', category='question', status='escalated')
    MailMessage.objects.filter(pk=old.pk).update(fetched_at=timezone.now() - timedelta(days=181))
    assert poczta.retention() == 1
    old.refresh_from_db()
    assert old.body == '' and old.body_deleted_at and old.subject
    assert poczta.retention() == 0


def test_plan_dry_run_writes_nothing_and_sends_nothing(mailbox, monkeypatch):
    monkeypatch.setenv('MAIL_AGENT_AUTOSEND', 'true')
    monkeypatch.setattr(poczta, 'ask', model())
    FakeIMAP.boxes = {1: raw_mail(message_id='<p1@x>'), 2: raw_mail(sender='Red <red@gazeta.pl>', subject='Komentarz', message_id='<p2@x>')}
    rows = poczta.plan(limit=20)
    assert len(rows) == 2 and rows[0]['action'] == 'send' and rows[0]['reply'] == GOOD_REPLY and rows[0]['checks'] == []
    assert MailMessage.objects.count() == 0 and FakeSMTP.sent == [] and MailboxState.objects.get(mailbox=BOX).last_uid == 0


def test_check_poczta_repairs_first_then_alarms(mailbox, monkeypatch):
    from news import poczta_kontrola as kontrola
    now = timezone.now()
    ctx = SimpleNamespace(now=now)
    state = MailboxState.objects.create(mailbox=BOX, last_ok_at=now - timedelta(hours=5), last_error='OSError', last_error_at=now - timedelta(minutes=5), consecutive_errors=3)
    retried = []
    monkeypatch.setattr(kontrola, 'retrigger', lambda name: retried.append(name) or True)
    assert kontrola.check_poczta(ctx) == [] and retried == [BOX]  # najpierw naprawa
    alarms = kontrola.check_poczta(ctx)
    assert len(alarms) == 1 and alarms[0]['key'] == 'poczta:SPIN' and alarms[0]['severity'] == 'critical' and alarms[0]['repairer'] == 'poczta-10m'
    assert 'tajne' not in str(alarms[0]) and 'MAILBOX_SPIN_IMAP_PASSWORD' in alarms[0]['instruction']
    state.last_ok_at = now
    state.save()
    assert kontrola.check_poczta(ctx) == [] and cache.get(kontrola.REPAIR_KEY + BOX) is None
    state.last_ok_at, state.last_error_at = now - timedelta(hours=1), now - timedelta(minutes=10)
    state.save()
    assert kontrola.check_poczta(ctx) == []  # poniżej 2 h: cisza


def test_command_stan_and_plan(mailbox, monkeypatch, capsys):
    from django.core.management import call_command
    monkeypatch.setattr(poczta, 'ask', model())
    FakeIMAP.boxes = {1: raw_mail(message_id='<c1@x>')}
    call_command('poczta', '--stan')
    out = capsys.readouterr().out
    assert 'spin.clinic (SPIN): IMAP ok, SMTP ok' in out and 'wyłączona (MAIL_AGENT_AUTOSEND)' in out and 'tajne' not in out
    call_command('poczta', '--plan')
    out = capsys.readouterr().out
    assert 'kategoria: question (90)' in out and 'szkic:' in out and 'nic nie wysłano' in out and FakeSMTP.sent == []


def test_registry_schedule_contract_consistency():
    from news import agent_registry, daily_schedule, raport_petli, tasks
    assert agent_registry.REGISTRY['poczta']['task'] == 'news.tasks.poczta_task'
    assert agent_registry.REGISTRY['poczta-digest']['task'] == 'news.tasks.poczta_digest_task'
    for key in ('poczta-10m', 'poczta-digest-daily'):
        assert hasattr(tasks, daily_schedule.BEAT_PLAN[key][0])
    contract = raport_petli.BY_KEY['poczta']
    assert set(contract['beats']) <= set(daily_schedule.BEAT_PLAN) and contract['registry'] == 'poczta'
    from news.duty_extra import CHECKS
    assert any(c.__name__ == 'check_poczta' for c in CHECKS)
