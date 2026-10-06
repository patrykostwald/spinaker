"""Poczta (właściciel 6.10: „sam nie wysyłam maili - agent czyta skrzynki projektów i odpowiada”).

Skrzynki z MAILBOXES (nazwy rozdzielone przecinkiem); dane każdej tylko ze zmiennych środowiska
MAILBOX_<NAZWA>_IMAP_HOST / _IMAP_USER / _IMAP_PASSWORD (odczyt) i MAILBOX_<NAZWA>_SMTP_HOST / _SMTP_USER /
_SMTP_PASSWORD (odpowiedzi), opcjonalnie _IMAP_PORT (993), _SMTP_PORT (465), _SMTP_FROM, _LABEL. Skrzynka bez
kompletu zmiennych jest wyłączona; sekrety nigdy nie trafiają do logów, bazy ani raportów (tylko nazwy zmiennych).

Co 10 minut: nowe wiadomości po UID (idempotentnie, z kontrolą UIDVALIDITY), minimalne metadane i treść w bazie
(treść usuwana po 180 dniach), klasyfikacja jednym darmowym modelem (Inception pierwszy, potem łańcuch Konsylium):
sprostowanie, pytanie czytelnika, prasa, partner, instytucja, spam, inne. Dla bezpiecznych kategorii model pisze
szkic odpowiedzi; szkic przechodzi kontrolę Recenzenta (po polsku, krótki myślnik, bez obietnic pieniędzy, bez stanowisk
prawnych, bez danych osobowych, linki tylko do naszych stron) i idzie w wątku (In-Reply-To) przez SMTP tej skrzynki.

Twarde zasady: tylko odpowiedzi na wiadomości przychodzące (nigdy pierwszy kontakt handlowy, PKE art. 398); automaty,
listy i własne adresy pomijane; instytucje, groźby prawne, pieniądze i wszystko niepewne (słowa ryzyka, pewność poniżej
progu, zarzuty kontroli) -> bez wysyłki, do właściciela w jednym dziennym zestawieniu z proponowanym szkicem;
najwyżej MAIL_AGENT_DAILY_LIMIT (20) odpowiedzi na skrzynkę dziennie, jedna odpowiedź na wątek na 24 h;
wyłącznik MAIL_AGENT_AUTOSEND (domyślnie false: szkice tylko w zestawieniu, dopóki właściciel nie włączy)."""
from __future__ import annotations

import hashlib
import html
import imaplib
import logging
import os
import re
import smtplib
import ssl
from datetime import timedelta
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.utils import timezone

from news.poczta_models import CATEGORIES, SAFE_CATEGORIES, MailboxState, MailMessage

logger = logging.getLogger(__name__)
WARSAW = ZoneInfo('Europe/Warsaw')
RETENTION_DAYS = 180
FETCH_LIMIT = 50
CLASSIFY_LIMIT = 20
MAX_CLASSIFY_ATTEMPTS = 6  # ~1 h bez wolnego modelu -> do właściciela jako „inne”
MIN_CONFIDENCE = 70
THREAD_WINDOW = timedelta(hours=24)
IMAP_KEYS = ('IMAP_HOST', 'IMAP_USER', 'IMAP_PASSWORD')
SMTP_KEYS = ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD')
CATEGORY_KEYS = tuple(key for key, _ in CATEGORIES)
CATEGORY_LABELS = dict(CATEGORIES)
AUTOMATON_LOCAL = ('mailer-daemon', 'postmaster', 'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'notifications',
                   'notification', 'newsletter', 'bounce', 'bounces', 'alerts', 'alert')
RISK = re.compile(r'(\bpozw(em|ie|y|u|ów|ać|iemy|any|ana|anie)\b|\bsąd(u|owi|em|zie|y|ów|om|ami|ach|ow\w*)?\b|kancelari|adwokat|'
                  r'radc[ay] prawn|wezwanie|faktur|płatno|zapłat|przelew|odszkodowan|zadośćuczynien|\brodo\b|dan[ey] osobow|zniesławi|'
                  r'prokurat|policj|\burz[aą]d(u|owi|em|zie|y|ów|om|ami|ach|ow\w*)?\b|ministerstw|komisj|\bugod|roszczen|windykac|'
                  r'komorni|ultimatum|\bskarg)', re.I)
PROMISES = re.compile(r'(zapłac|zwróc\w*\s+(pieni|koszt|kwot)|gwarantuj|odszkodowan|zobowiązuj|wypłac|refundac|rekompensat|'
                      r'zadośćuczyni|bezpłatn\w* otrzyma|rabat|zniżk|cennik|\bcen[aęy]\b)', re.I)
LEGAL = re.compile(r'(stanowisk\w* prawn|nasz\w* prawnik|bezprawn|narusz\w* praw|\bpozw(em|ie|y|u|ów|ać|iemy|any|ana|anie)\b|'
                   r'\bsąd(u|owi|em|zie|y|ów|om|ami|ach|ow\w*)?\b|art\.\s?\d|przepis\w*|zgodnie z ustaw|kodeks)', re.I)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'(?<!\d)(?:\+?48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)')
PESEL_RE = re.compile(r'(?<!\d)\d{11}(?!\d)')
URL_RE = re.compile(r'https?://([\w.-]+)', re.I)
POLISH_WORDS = {'nie', 'jest', 'się', 'dziękujemy', 'dziękuję', 'za', 'do', 'na', 'w', 'z', 'i', 'że', 'to', 'pana', 'pani',
                'państwa', 'wiadomość', 'odpowiedź', 'pozdrawiamy', 'sprawdzimy', 'przekazaliśmy', 'dzień', 'dobry'}
PROMPT = (
    'Jesteś agentem Poczty serwisów spin.clinic (diagnozy spinu w wypowiedziach polityków, ta sama miara dla każdej strony), '
    'przeszłość.today (narzędzie OSINT dla dziennikarzy), zbudujmi.com (strony dla małych firm) i iapply (operator, sp. z o.o.). '
    'Dostajesz jedną wiadomość przychodzącą. Zaklasyfikuj ją do jednej kategorii: correction (sprostowanie, skarga na diagnozę '
    'albo treść), question (pytanie czytelnika o serwis, metodę, konto), press (dziennikarz, redakcja, prośba o komentarz lub '
    'dane), partner (przychodzące zapytanie o współpracę, ofertę, raport, stronę), institution (urząd, sąd, kancelaria, '
    'partia, pismo oficjalne, wezwanie, RODO, pieniądze), spam (reklama, phishing, masowa wysyłka), other (nie pasuje). '
    'confidence 0-100: jak pewna jest kategoria. reason: jedno zdanie po polsku. '
    'reply: tylko dla correction, question, press, partner - krótka, uprzejma odpowiedź po polsku (3-7 zdań, forma „Państwo”), '
    'która potwierdza odbiór, odpowiada na to, co da się odpowiedzieć z ogólnej wiedzy o serwisie, a resztę zapowiada do '
    'sprawdzenia przez zespół (bez terminu). Zasady odpowiedzi: krótki myślnik „-”, nigdy długa kreska; bez obietnic pieniędzy, '
    'rabatów, cen, odszkodowań; bez ocen prawnych i stanowisk prawnych; bez danych osobowych i numerów; bez linków poza '
    'spin.clinic, przeszlosc.today, zbudujmi.com; przy sprostowaniu: dziękujemy, sprawdzimy diagnozę tą samą miarą, nie '
    'obiecujemy zmiany wyniku; przy prasie: potwierdzenie i zapowiedź kontaktu zespołu; przy partnerze: podziękowanie i '
    'zapowiedź odpowiedzi zespołu, bez cen. Dla institution, spam, other reply ma być pusty. Odpowiadasz tylko JSON-em.')
SCHEMA = {'type': 'object', 'properties': {
    'category': {'type': 'string', 'enum': list(CATEGORY_KEYS)},
    'confidence': {'type': 'integer'},
    'reason': {'type': 'string'},
    'reply': {'type': 'string'}},
    'required': ['category', 'confidence', 'reason', 'reply']}


class MailboxError(RuntimeError):
    pass


# --- konfiguracja (tylko nazwy zmiennych; wartości nigdy nie opuszczają procesu) ------------------------------------

def _env(name, default=''):
    return os.environ.get(name, default).strip()


def names():
    return [n.strip().upper().replace('-', '_').replace('.', '_') for n in _env('MAILBOXES').split(',') if n.strip()]


def env_name(name, key):
    return f'MAILBOX_{name}_{key}'


def _port(name, key, default):
    try:
        return int(_env(env_name(name, key)) or default)
    except ValueError:
        return default


def config(name):
    get = lambda key: _env(env_name(name, key))  # noqa: E731
    imap_user = get('IMAP_USER')
    smtp_from = get('SMTP_FROM') or get('SMTP_USER') or imap_user
    return {'name': name, 'label': get('LABEL') or name.lower().replace('_', '.'),
            'imap_host': get('IMAP_HOST'), 'imap_port': _port(name, 'IMAP_PORT', 993), 'imap_user': imap_user,
            'imap_password': get('IMAP_PASSWORD'),
            'smtp_host': get('SMTP_HOST'), 'smtp_port': _port(name, 'SMTP_PORT', 465), 'smtp_user': get('SMTP_USER'),
            'smtp_password': get('SMTP_PASSWORD'), 'smtp_from': smtp_from,
            'address': parseaddr(smtp_from)[1].lower() or imap_user.lower()}


def missing(name, keys=IMAP_KEYS + SMTP_KEYS):
    return [env_name(name, key) for key in keys if not _env(env_name(name, key))]


def imap_ready(cfg):
    return all(cfg[k] for k in ('imap_host', 'imap_user', 'imap_password'))


def smtp_ready(cfg):
    return all(cfg[k] for k in ('smtp_host', 'smtp_user', 'smtp_password', 'smtp_from'))


def enabled():
    return _env('MAIL_AGENT_ENABLED', 'true').lower() != 'false' and bool(names())


def autosend():
    return _env('MAIL_AGENT_AUTOSEND', 'false').lower() in ('1', 'true', 'yes')


def daily_limit():
    try:
        return max(0, int(_env('MAIL_AGENT_DAILY_LIMIT') or 20))
    except ValueError:
        return 20


def allowed_domains():
    return tuple(d.strip().lower() for d in (_env('MAIL_AGENT_DOMAINS') or 'spin.clinic,przeszlosc.today,zbudujmi.com').split(',') if d.strip())


def own_addresses():
    return {config(n)['address'] for n in names() if config(n)['address']}


# --- odczyt IMAP ----------------------------------------------------------------------------------------------------

def _text(message):
    try:
        part = message.get_body(preferencelist=('plain', 'html'))
    except Exception:  # noqa: BLE001 - uszkodzone MIME: zostaje temat
        part = None
    if part is None:
        return ''
    try:
        content = part.get_content()
    except Exception:  # noqa: BLE001
        payload = part.get_payload(decode=True) or b''
        content = payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
    if not isinstance(content, str):
        return ''
    if part.get_content_subtype() == 'html':
        content = re.sub(r'(?is)<(script|style).*?</\1>', ' ', content)
        content = re.sub(r'(?i)<br\s*/?>|</p>|</div>', '\n', content)
        content = html.unescape(re.sub(r'<[^>]+>', ' ', content))
    content = re.sub(r'[ \t]+', ' ', content)
    return re.sub(r'\n{3,}', '\n\n', content).strip()[:20000]


def _header(message, name):
    try:
        return str(message.get(name, '') or '').strip()
    except Exception:  # noqa: BLE001 - błędne kodowanie nagłówka
        return ''


def _when(value):
    try:
        parsed = parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalized_subject(subject):
    return re.sub(r'^\s*((re|odp|fwd?|fw|pd)\s*:\s*)+', '', subject or '', flags=re.I).strip().lower()[:200]


def thread_key(sender_address, subject):
    return hashlib.sha1(f'{sender_address.lower()}|{normalized_subject(subject)}'.encode()).hexdigest()[:40]


def _automaton(message, address):
    local = address.split('@', 1)[0].lower()
    return (_header(message, 'Auto-Submitted').lower() not in ('', 'no')
            or _header(message, 'Precedence').lower() in ('bulk', 'list', 'junk')
            or bool(_header(message, 'List-Id')) or bool(_header(message, 'List-Unsubscribe'))
            or bool(_header(message, 'X-Auto-Response-Suppress'))
            or any(local == w or local.startswith(w + '+') or local.startswith(w + '-') for w in AUTOMATON_LOCAL))


def parse(raw: bytes) -> dict:
    message = message_from_bytes(raw, policy=policy.default)
    sender = _header(message, 'From')[:320]
    address = parseaddr(sender)[1].lower()[:254]
    subject = _header(message, 'Subject')[:500]
    return {'message_id': _header(message, 'Message-ID')[:512], 'in_reply_to': _header(message, 'In-Reply-To')[:512],
            'references': _header(message, 'References')[:4000], 'sender': sender, 'sender_address': address,
            'subject': subject, 'body': _text(message), 'auto_generated': _automaton(message, address),
            'received_at': _when(_header(message, 'Date')), 'thread_key': thread_key(address, subject)}


def _uidvalidity(client):
    try:
        status, data = client.response('UIDVALIDITY')
    except Exception:  # noqa: BLE001
        return ''
    return (data[0].decode() if data and data[0] else '')[:32]


def _fetch_raw(client, uid):
    status, result = client.uid('fetch', str(uid), '(BODY.PEEK[])')
    if status != 'OK' or not result:
        return None
    for item in result:
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
    return None


def fetch(cfg, now=None, limit=FETCH_LIMIT, store=True, newest=0):
    """Nowe wiadomości ze skrzynki (UID powyżej ostatniego; newest>0: ostatnie N niezależnie od stanu, bez zapisu).
    Zwraca {'scanned', 'created', 'messages'}; błąd połączenia zapisuje w stanie skrzynki i podnosi MailboxError."""
    now = now or timezone.now()
    name = cfg['name']
    state, _ = MailboxState.objects.get_or_create(mailbox=name)
    created, scanned, messages = 0, 0, []
    client = None
    try:
        client = imaplib.IMAP4_SSL(cfg['imap_host'], cfg['imap_port'], ssl_context=ssl.create_default_context())
        client.login(cfg['imap_user'], cfg['imap_password'])
        status, _data = client.select('INBOX', readonly=True)
        if status != 'OK':
            raise MailboxError('imap_inbox_unavailable')
        validity = _uidvalidity(client)
        if store and validity and validity != state.uidvalidity:
            state.uidvalidity, state.last_uid = validity, 0  # nowa numeracja UID: czytamy od początku, duplikaty odrzuca Message-ID
        if newest:
            status, data = client.uid('search', None, 'ALL')
            uids = [int(u) for u in (data[0].split() if status == 'OK' and data and data[0] else [])][-newest:]
        else:
            status, data = client.uid('search', None, f'UID {state.last_uid + 1}:*')
            uids = sorted(int(u) for u in (data[0].split() if status == 'OK' and data and data[0] else []) if int(u) > state.last_uid)[:limit]
        for uid in uids:
            raw = _fetch_raw(client, uid)
            scanned += 1
            if raw is None:
                continue
            parsed = parse(raw)
            if store:
                if _store(name, uid, parsed, now):
                    created += 1
                state.last_uid = max(state.last_uid, uid)
            else:
                messages.append({'uid': uid, **parsed})
        state.last_ok_at, state.last_error, state.consecutive_errors = now, '', 0
        state.save()
        return {'scanned': scanned, 'created': created, 'messages': messages}
    except (OSError, imaplib.IMAP4.error, MailboxError, ssl.SSLError) as error:
        state.last_error = type(error).__name__[:200]  # nigdy treść błędu: może zawierać login
        state.last_error_at = now
        state.consecutive_errors = min(state.consecutive_errors + 1, 999)
        state.save()
        logger.warning('poczta %s: imap failed (%s)', name, type(error).__name__)
        raise MailboxError(type(error).__name__) from error
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass


def _store(name, uid, parsed, now):
    if parsed['message_id'] and MailMessage.objects.filter(mailbox=name, message_id=parsed['message_id']).exists():
        return False
    try:
        with transaction.atomic():
            MailMessage.objects.create(mailbox=name, uid=uid, fetched_at=now, **parsed)
    except IntegrityError:
        return False
    return True


# --- klasyfikacja i szkic ----------------------------------------------------------------------------------------

def ask(data):
    """Jeden darmowy model (Inception pierwszy, potem Konsylium). Zwraca (odpowiedź, członek); WindowClosed bez modelu."""
    from news import agents_common as common
    return common.ask_any(PROMPT, data, SCHEMA)


def payload(message, cfg):
    return {'skrzynka': cfg['label'], 'od': message['sender_address'] if isinstance(message, dict) else message.sender_address,
            'temat': message['subject'] if isinstance(message, dict) else message.subject,
            'treść': (message['body'] if isinstance(message, dict) else message.body)[:6000]}


def fix_dashes(text):
    return re.sub(r'\s*[—–]\s*', ' - ', text or '').strip()


def check_reply(text, cfg):
    """Kontrola Recenzenta dla szkicu: lista zarzutów (pusta = można wysłać). Reguły stałe, bez modelu."""
    problems = []
    text = text or ''
    if len(text) < 40:
        problems.append('za krótka')
    if len(text) > 1800:
        problems.append('za długa')
    if '—' in text or '–' in text:
        problems.append('długa kreska')
    words = {w.strip('.,!?:;„”"()').lower() for w in text.split()}
    if len(words & POLISH_WORDS) < 2 and not re.search(r'[ąćęłńóśźż]', text, re.I):
        problems.append('nie po polsku')
    if PROMISES.search(text):
        problems.append('obietnica pieniędzy lub cen')
    if LEGAL.search(text):
        problems.append('stanowisko prawne')
    foreign = [a for a in EMAIL_RE.findall(text) if a.lower() != cfg['address']]
    if foreign:
        problems.append('adres e-mail w treści')
    if PHONE_RE.search(text):
        problems.append('numer telefonu')
    if PESEL_RE.search(text):
        problems.append('ciąg 11 cyfr (PESEL?)')
    allowed = allowed_domains()
    for host in URL_RE.findall(text):
        host = host.lower()
        if not any(host == d or host.endswith('.' + d) for d in allowed):
            problems.append('obcy link')
            break
    return problems


def _clamp(value):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def heuristic(message_dict, cfg):
    """Bez modelu: tylko pewne przypadki (automat, własny adres, brak nadawcy)."""
    if message_dict['sender_address'] in own_addresses() or message_dict['sender_address'] == cfg['address']:
        return 'other', 'własna skrzynka'
    if message_dict['auto_generated']:
        return 'other', 'automat (Auto-Submitted, lista, mailer-daemon)'
    if not message_dict['sender_address']:
        return 'spam', 'brak adresu nadawcy'
    return '', ''


def classify(message, cfg):
    """Kategoria, pewność, powód i szkic dla wiadomości (model albo heurystyka). Zwraca dict; WindowClosed przepuszcza."""
    as_dict = message if isinstance(message, dict) else {
        'sender_address': message.sender_address, 'auto_generated': message.auto_generated, 'subject': message.subject, 'body': message.body}
    category, reason = heuristic(as_dict, cfg)
    if category:
        return {'category': category, 'confidence': 100, 'reason': reason, 'reply': '', 'model': 'heurystyka'}
    answer, member = ask(payload(message, cfg))
    category = answer.get('category') if answer.get('category') in CATEGORY_KEYS else 'other'
    reply = fix_dashes(answer.get('reply') or '') if category in SAFE_CATEGORIES else ''
    return {'category': category, 'confidence': _clamp(answer.get('confidence')), 'reason': str(answer.get('reason') or '')[:300],
            'reply': reply[:4000], 'model': member[1] if isinstance(member, (tuple, list)) and len(member) > 1 else str(member)}


def day_start(now):
    return now.astimezone(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)


def replied_today(name, now):
    return MailMessage.objects.filter(mailbox=name, status='replied', reply_sent_at__gte=day_start(now)).count()


def decision(message, cfg, now, checks=None):
    """(co zrobić, powód): 'send' | 'escalate' | 'skip'. Bez zapisu i bez sieci; checks = zarzuty kontroli szkicu."""
    if message.category == 'spam':
        return 'skip', 'spam'
    if message.category == 'other' and message.confidence >= 100 and message.category_reason.startswith(('własna', 'automat')):
        return 'skip', message.category_reason
    if message.category not in SAFE_CATEGORIES:
        return 'escalate', CATEGORY_LABELS.get(message.category, message.category).lower()
    if message.confidence < MIN_CONFIDENCE:
        return 'escalate', f'pewność {message.confidence} poniżej {MIN_CONFIDENCE}'
    hit = RISK.search(f'{message.subject}\n{message.body}')
    if hit:
        return 'escalate', f'słowo ryzyka: {hit.group(0).lower()}'
    if not message.reply_draft:
        return 'escalate', 'brak szkicu'
    if checks:
        return 'escalate', 'kontrola szkicu: ' + ', '.join(checks)
    if not message.sender_address:
        return 'escalate', 'brak adresu nadawcy'
    if MailMessage.objects.filter(mailbox=message.mailbox, thread_key=message.thread_key, status='replied',
                                  reply_sent_at__gte=now - THREAD_WINDOW).exclude(pk=message.pk).exists():
        return 'skip', 'wątek: odpowiedź w ostatnich 24 h'
    if replied_today(message.mailbox, now) >= daily_limit():
        return 'escalate', f'limit dzienny {daily_limit()} odpowiedzi'
    if not autosend():
        return 'escalate', 'MAIL_AGENT_AUTOSEND wyłączone (szkic do wglądu)'
    if not smtp_ready(cfg):
        return 'escalate', 'brak SMTP: ' + ', '.join(missing(message.mailbox, SMTP_KEYS))
    return 'send', ''


def signature(cfg):
    return (f'\n\n-- \n{cfg["label"]}\nTę odpowiedź przygotował automatyczny asystent poczty, a zespół ją sprawdza. '
            'Jeśli coś jest niejasne, proszę napisać ponownie w tym samym wątku.')


def _reply_subject(subject):
    subject = (subject or '').strip()
    return subject if re.match(r'^\s*(re|odp)\s*:', subject, re.I) else ('Re: ' + subject if subject else 'Re: Państwa wiadomość')


def build_reply(message, cfg, text):
    email = EmailMessage()
    email['From'] = cfg['smtp_from']
    email['To'] = message.sender if parseaddr(message.sender)[1] else message.sender_address
    email['Subject'] = _reply_subject(message.subject)
    if message.message_id:
        email['In-Reply-To'] = message.message_id
        email['References'] = ' '.join(x for x in (message.references, message.message_id) if x)
    domain = cfg['address'].split('@', 1)[1] if '@' in cfg['address'] else None
    email['Message-ID'] = make_msgid(domain=domain)
    email['Auto-Submitted'] = 'auto-replied'  # RFC 3834: automaty nie odpowiadają na nasze odpowiedzi
    email.set_content(text + signature(cfg))
    return email


def send(message, cfg, text):
    email = build_reply(message, cfg, text)
    context = ssl.create_default_context()
    if cfg['smtp_port'] == 465:
        with smtplib.SMTP_SSL(cfg['smtp_host'], cfg['smtp_port'], timeout=30, context=context) as client:
            client.login(cfg['smtp_user'], cfg['smtp_password'])
            client.send_message(email)
    else:
        with smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=30) as client:
            client.starttls(context=context)
            client.login(cfg['smtp_user'], cfg['smtp_password'])
            client.send_message(email)
    return email['Message-ID']


def process(message, cfg, now):
    """Klasyfikacja (gdy brak), decyzja i wykonanie dla jednej wiadomości. Zwraca końcowy status."""
    from news.agents_common import WindowClosed
    if not message.category:
        try:
            result = classify(message, cfg)
        except WindowClosed:
            message.classify_attempts += 1
            if message.classify_attempts >= MAX_CLASSIFY_ATTEMPTS:
                message.category, message.category_reason, message.confidence = 'other', 'brak wolnego modelu do klasyfikacji', 0
                message.model_name = ''
            else:
                message.save(update_fields=['classify_attempts'])
                return 'new'
        else:
            message.category, message.confidence = result['category'], result['confidence']
            message.category_reason, message.reply_draft, message.model_name = result['reason'], result['reply'], result['model'][:64]
            message.reply_checks = check_reply(message.reply_draft, cfg) if message.reply_draft else []
    action, reason = decision(message, cfg, now, message.reply_checks)
    if action == 'send':
        try:
            message.reply_message_id = send(message, cfg, message.reply_draft)[:512]
            message.status, message.status_reason, message.reply_sent_at = 'replied', 'odpowiedź automatyczna', now
        except (OSError, smtplib.SMTPException, ssl.SSLError) as error:
            logger.warning('poczta %s: smtp failed (%s)', cfg['name'], type(error).__name__)
            message.status, message.status_reason = 'failed', 'SMTP: ' + type(error).__name__
            message.escalated_at = now
    elif action == 'escalate':
        message.status, message.status_reason, message.escalated_at = 'escalated', reason, now
    else:
        message.status, message.status_reason = 'skipped', reason
    message.save()
    return message.status


# --- przebieg, zestawienie, retencja ------------------------------------------------------------------------------

def run(now=None):
    if not enabled():
        return {'status': 'disabled'}
    now = now or timezone.now()
    out = {'status': 'ok', 'mailboxes': 0, 'received': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'waiting': 0, 'errors': 0}
    for name in names():
        cfg = config(name)
        if not imap_ready(cfg):
            continue  # skrzynka bez kompletu zmiennych: wyłączona (nazwy brakujących pokazuje `poczta --stan`)
        out['mailboxes'] += 1
        try:
            out['received'] += fetch(cfg, now)['created']
        except MailboxError:
            out['errors'] += 1
        rows = MailMessage.objects.filter(mailbox=name, status='new').order_by('fetched_at', 'pk')[:CLASSIFY_LIMIT]
        for message in rows:
            status = process(message, cfg, now)
            key = {'replied': 'replied', 'escalated': 'escalated', 'failed': 'escalated', 'skipped': 'skipped', 'new': 'waiting'}[status]
            out[key] += 1
    if not out['mailboxes']:
        out['status'] = 'not_configured'
    elif out['errors'] and out['errors'] == out['mailboxes']:
        out['status'] = 'failed'
    return out


def retention(now=None):
    now = now or timezone.now()
    rows = MailMessage.objects.filter(fetched_at__lt=now - timedelta(days=RETENTION_DAYS), body_deleted_at__isnull=True)
    return rows.update(body='', reply_draft='', body_deleted_at=now)


def _snippet(text, limit=300):
    return re.sub(r'\s+', ' ', text or '').strip()[:limit]


def digest_text(rows, now):
    lines = [f'Poczta - wiadomości do Twojej decyzji ({now.astimezone(WARSAW):%d.%m %H:%M}). '
             'Agent nie wysłał odpowiedzi; przy każdej jest proponowany szkic (jeśli powstał).', '']
    for i, row in enumerate(rows, 1):
        label = config(row.mailbox)['label']
        lines.append(f'{i}. [{label}] od {row.sender_address or "(brak adresu)"} · temat: {row.subject or "(bez tematu)"}')
        lines.append(f'   kategoria: {CATEGORY_LABELS.get(row.category, row.category or "brak")} ({row.confidence}) · powód: {row.status_reason}')
        if row.body:
            lines.append(f'   fragment: {_snippet(row.body)}')
        if row.reply_draft:
            lines.append('   proponowany szkic:')
            lines += ['      ' + l for l in fix_dashes(row.reply_draft).splitlines() if l.strip()]
            if row.reply_checks:
                lines.append('   zarzuty kontroli: ' + ', '.join(row.reply_checks))
        lines.append('')
    lines.append(f'Odpowiedzi automatyczne dziś: {sum(replied_today(n, now) for n in names())} · '
                 f'włącznik wysyłki MAIL_AGENT_AUTOSEND: {"włączony" if autosend() else "wyłączony"} · '
                 f'limit na skrzynkę: {daily_limit()}')
    lines.append('Stan: python manage.py poczta --stan')
    return '\n'.join(lines)


def digest(now=None):
    """Jeden mail dziennie do właściciela (important=True) z wiadomościami bez automatycznej odpowiedzi i szkicami."""
    now = now or timezone.now()
    rows = list(MailMessage.objects.filter(status__in=('escalated', 'failed'), digest_sent_at__isnull=True).order_by('mailbox', 'fetched_at'))
    if not rows:
        return {'status': 'idle', 'items': 0}
    from news.raport_petli import recipient
    from news.social_publish import _mail
    to = recipient()
    sent = bool(to) and _mail(to, f'spin.clinic · Poczta: {len(rows)} wiadomości do decyzji', digest_text(rows, now), important=True)
    if sent:
        MailMessage.objects.filter(pk__in=[r.pk for r in rows]).update(digest_sent_at=now)
    return {'status': 'ok' if sent else 'failed', 'items': len(rows), 'sent': bool(sent)}


def counts(now=None, hours=24):
    now = now or timezone.now()
    since = now - timedelta(hours=hours)
    rows = MailMessage.objects.filter(fetched_at__gte=since)
    return {'received': rows.count(), 'replied': rows.filter(status='replied').count(),
            'escalated': rows.filter(status__in=('escalated', 'failed')).count(), 'skipped': rows.filter(status='skipped').count(),
            'waiting': rows.filter(status='new').count()}


def report_lines(now=None):
    """Linia dla Raportu pętli: odebrane, odpowiedziane automatycznie, do właściciela (24 h i 7 dni)."""
    now = now or timezone.now()
    if not names():
        return ['Poczta: brak skrzynek (MAILBOXES puste).']
    day, week = counts(now, 24), counts(now, 24 * 7)
    lines = [f"Odebrane 24 h: {day['received']} (7 dni: {week['received']}) · odpowiedziane automatycznie: {day['replied']} "
             f"({week['replied']}) · do właściciela: {day['escalated']} ({week['escalated']}) · pominięte: {day['skipped']} ({week['skipped']})"
             f" · wysyłka: {'włączona' if autosend() else 'wyłączona (MAIL_AGENT_AUTOSEND)'}"]
    for name in names():
        state = MailboxState.objects.filter(mailbox=name).first()
        cfg = config(name)
        if not imap_ready(cfg):
            lines.append(f"- {cfg['label']}: wyłączona, brak {', '.join(missing(name, IMAP_KEYS))}")
        elif state and state.last_error and (not state.last_ok_at or state.last_error_at and state.last_error_at > state.last_ok_at):
            lines.append(f"- {cfg['label']}: błąd IMAP {state.last_error} od {state.last_error_at.astimezone(WARSAW):%d.%m %H:%M}")
    return lines


def stan(now=None):
    now = now or timezone.now()
    boxes = []
    for name in names():
        cfg = config(name)
        state = MailboxState.objects.filter(mailbox=name).first()
        rows = MailMessage.objects.filter(mailbox=name)
        boxes.append({'name': name, 'label': cfg['label'], 'imap': imap_ready(cfg), 'smtp': smtp_ready(cfg), 'missing': missing(name),
                      'last_ok_at': state.last_ok_at if state else None, 'last_error': state.last_error if state else '',
                      'last_error_at': state.last_error_at if state else None, 'last_uid': state.last_uid if state else 0,
                      'messages': rows.count(), 'waiting': rows.filter(status='new').count(),
                      'replied_today': replied_today(name, now), 'escalated_open': rows.filter(status__in=('escalated', 'failed'), digest_sent_at__isnull=True).count()})
    return {'enabled': enabled(), 'autosend': autosend(), 'daily_limit': daily_limit(), 'mailboxes': boxes,
            'missing_global': [] if names() else ['MAILBOXES'], 'counts_24h': counts(now)}


def plan(limit=20):
    """Próba na ostatnich wiadomościach każdej skrzynki: klasyfikacja i szkic, bez zapisu i bez wysyłki."""
    from news.agents_common import WindowClosed
    now = timezone.now()
    out = []
    for name in names():
        cfg = config(name)
        if not imap_ready(cfg):
            out.append({'mailbox': name, 'error': 'brak ' + ', '.join(missing(name, IMAP_KEYS))})
            continue
        try:
            fetched = fetch(cfg, now, store=False, newest=limit)
        except MailboxError as error:
            out.append({'mailbox': name, 'error': f'IMAP: {error}'})
            continue
        for item in fetched['messages']:
            try:
                result = classify(item, cfg)
            except WindowClosed as error:
                result = {'category': '', 'confidence': 0, 'reason': f'brak modelu: {str(error)[:120]}', 'reply': '', 'model': ''}
            draft = MailMessage(mailbox=name, uid=item['uid'], sender=item['sender'], sender_address=item['sender_address'], subject=item['subject'],
                                body=item['body'], thread_key=item['thread_key'], category=result['category'], confidence=result['confidence'],
                                category_reason=result['reason'], reply_draft=result['reply'])
            checks = check_reply(draft.reply_draft, cfg) if draft.reply_draft else []
            action, reason = decision(draft, cfg, now, checks) if draft.category else ('escalate', 'brak klasyfikacji')
            out.append({'mailbox': name, 'uid': item['uid'], 'from': item['sender_address'], 'subject': item['subject'][:120],
                        'category': result['category'], 'confidence': result['confidence'], 'reason': result['reason'],
                        'action': action, 'why': reason, 'checks': checks, 'reply': result['reply'], 'model': result['model']})
    return out
