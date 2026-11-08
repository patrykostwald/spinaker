"""Poczta wychodząca (właściciel 7.10: „agenci sami wysyłają potrzebne wnioski i zapytania”).

Kolejka to pliki Markdown w katalogu deploy/poczta-wychodzaca (w kontenerze: /app/poczta-wychodzaca, kopiowane przez
skrypt wdrożenia; inny katalog: MAIL_OUTBOX_DIR). Każdy plik: nagłówek YAML między liniami „---” i treść listu.
Pola nagłówka: to (adres e-mail; pusty = czeka na adres), subject, mailbox (SPIN | IAPPLY | PATRYK, nazwa z MAILBOXES),
category (dostep-do-danych | instytucja | partner | odpowiedz), opcjonalnie: lang (PL | EN), attachments (nazwy plików
z tego katalogu, po przecinku), not_before (RRRR-MM-DD), hold (powód wstrzymania: list nigdy nie idzie), reply_to_item
(klucz wcześniejszego listu: wysyłka w jego wątku, dopiero po jego wysłaniu), contact_url (strona kontaktowa adresata,
gdy brak adresu), source (skąd adres). Pliki zaczynające się od „_” to opisy, nie listy.

Każdy list przed wysyłką: (a) kontrola Recenzenta i Prawnika - bez oferty handlowej przy pierwszym kontakcie (PKE art. 398),
bez obietnic pieniędzy, bez danych osobowych osób trzecich (adresy, telefony, PESEL), krótki myślnik, po polsku (chyba że
lang EN), ton rzeczowy, bez miejsc do uzupełnienia; miejsce {{PODPIS}} wypełnia MAIL_OUTBOX_SIGNER (imię i nazwisko,
funkcja osoby uprawnionej - nigdy w repozytorium); (b) duplikaty: rejestr MailOutboxLog i folder Wysłane skrzynki przez
IMAP (ten sam adresat i podobny temat w ostatnich 60 dniach -> pominięty; bez dostępu do folderu nie wysyłamy);
(c) limit dzienny MAIL_OUTBOX_DAILY_LIMIT (10 na skrzynkę). Wysyłka przez SMTP skrzynki, kopia do folderu Wysłane
(IMAP APPEND), wpis w rejestrze, pozycja w zestawieniu 7:10 do właściciela. `--plan` tylko pokazuje, co by poszło.

Dane spółki w podpisach pochodzą ze stron prawnych serwisów (frontend-spin: zasady korzystania, O nas) - nie wymyślamy."""
from __future__ import annotations

import logging
import mimetypes
import re
import time
from datetime import date, timedelta
from difflib import SequenceMatcher
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from news import poczta
from news.poczta_models import OUTBOX_CATEGORIES, MailOutboxLog

logger = logging.getLogger(__name__)
CATEGORY_KEYS = tuple(key for key, _ in OUTBOX_CATEGORIES)
MAILBOX_NAMES = ('SPIN', 'IAPPLY', 'PATRYK')
DUPLICATE_DAYS = 60
SIMILARITY = 0.6
SENT_SCAN = 60  # ostatnie wiadomości z folderu Wysłane do porównania tematu
PLACEHOLDER = '{{PODPIS}}'
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
SENT_FOLDERS = ('Sent', 'INBOX.Sent', 'Sent Items', 'Sent Messages', 'INBOX/Sent', 'Wysłane', 'INBOX.Wysłane', '[Gmail]/Sent Mail')
CLOSINGS = re.compile(r'^(z poważaniem|z wyrazami szacunku|pozdrawiam\w*|łączę (pozdrowienia|wyrazy szacunku)|kind regards|best regards|regards|sincerely),?\s*$', re.I)

COLD_OFFER = re.compile(r'(oferuj\w*|nasz[aą] ofert|ofert[aęy] handlow|bezpłatn\w+ (konta|konto|pilotaż\w*|dostęp\w*)|promocj|zamów|skorzystaj z|'
                        r'special offer|free trial|free accounts?)', re.I)
PROMISES = re.compile(r'(zapłacimy|zapłacić|gwarantuj\w*|zobowiązujemy się|odszkodowan|rekompensat|rabat|zniżk|nasz cennik|nasza cena|'
                      r'we will pay|we guarantee|discount|refund)', re.I)
BRACKETS = re.compile(r'\[[^\]\n]{3,}\]')
IDENTIFIERS = re.compile(r'(KRS|NIP|REGON|VAT\s*PL|AE:PL)[\s:]*[\dA-Z-]+', re.I)
UNPROFESSIONAL = re.compile(r'(!{2,}|\?{2,}|[\U0001F300-\U0001FAFF☀-➿])')
SHOUTING = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ .,-]{14,}$', re.M)

COMPANY = {'name': 'iapply sp. z o.o.', 'street': 'pl. Wolności 16', 'city': '61-739 Poznań', 'krs': '0001133291',
           'nip': '7831915094', 'regon': '529962488', 'capital': '50 000 zł',
           'court': 'Sąd Rejonowy Poznań - Nowe Miasto i Wilda w Poznaniu, VIII Wydział Gospodarczy KRS'}


class Item(dict):
    """Jeden list z kolejki (słownik z polami nagłówka, treścią i listą błędów składni)."""


# --- katalog i pliki ------------------------------------------------------------------------------------------------

def outbox_dir():
    custom = poczta._env('MAIL_OUTBOX_DIR')
    if custom:
        return Path(custom)
    candidates = (Path(settings.BASE_DIR).parent / 'deploy' / 'poczta-wychodzaca', Path(settings.BASE_DIR) / 'poczta-wychodzaca')
    return next((c for c in candidates if c.is_dir()), candidates[0])


def signer():
    return poczta._env('MAIL_OUTBOX_SIGNER')


def daily_limit():
    try:
        return max(0, int(poczta._env('MAIL_OUTBOX_DAILY_LIMIT') or 10))
    except ValueError:
        return 10


def _split(value):
    return [v.strip() for v in re.split(r'[,;]', value or '') if v.strip()]


def _date(value):
    try:
        return date.fromisoformat((value or '').strip()[:10]) if value else None
    except ValueError:
        return None


def parse_item(path: Path) -> Item:
    text = path.read_text(encoding='utf-8-sig')
    item = Item(key=path.stem, path=str(path), to='', subject='', mailbox='', category='', lang='PL', attachments=[],
                not_before=None, hold='', reply_to_item='', contact_url='', source='', body='', problems=[])
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not match:
        item['problems'].append('brak nagłówka YAML między liniami ---')
        item['body'] = poczta.fix_dashes(text)
        return item
    header, body = match.groups()
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if ':' not in line:
            item['problems'].append(f'niezrozumiała linia nagłówka: {line.strip()[:40]}')
            continue
        key, value = line.split(':', 1)
        key, value = key.strip().lower().replace('-', '_'), value.strip().strip('"').strip("'")
        if key == 'attachments':
            item['attachments'] = _split(value.strip('[]'))
        elif key == 'not_before':
            item['not_before'] = _date(value)
            if value and not item['not_before']:
                item['problems'].append('not_before nie jest datą RRRR-MM-DD')
        elif key in ('to', 'subject', 'mailbox', 'category', 'lang', 'hold', 'reply_to_item', 'contact_url', 'source'):
            item[key] = value
        else:
            item['problems'].append(f'nieznane pole: {key}')
    item['to'] = parseaddr(item['to'])[1].lower() if item['to'] else ''
    item['mailbox'] = item['mailbox'].upper().replace('-', '_').replace('.', '_')
    item['lang'] = (item['lang'] or 'PL').upper()
    item['body'] = poczta.fix_dashes(body.strip())
    if not item['subject']:
        item['problems'].append('brak tematu')
    if item['mailbox'] not in MAILBOX_NAMES:
        item['problems'].append(f"mailbox musi być jedną z: {', '.join(MAILBOX_NAMES)}")
    if item['category'] not in CATEGORY_KEYS:
        item['problems'].append(f"category musi być jedną z: {', '.join(CATEGORY_KEYS)}")
    if item['lang'] not in ('PL', 'EN'):
        item['problems'].append('lang: PL albo EN')
    if not item['body']:
        item['problems'].append('pusta treść')
    return item


def load_items(directory: Path | None = None):
    directory = directory or outbox_dir()
    if not directory.is_dir():
        return []
    return [parse_item(p) for p in sorted(directory.glob('*.md')) if not p.name.startswith('_')]


# --- podpisy -----------------------------------------------------------------------------------------------------------

def signature(cfg, lang='PL'):
    """Stopka skrzynki: MAILBOX_<NAZWA>_SIGNATURE (literalne \\n to nowa linia) albo szablon z danymi spółki ze stron prawnych."""
    custom = poczta._env(poczta.env_name(cfg['name'], 'SIGNATURE'))
    if custom:
        return '\n\n-- \n' + custom.replace('\\n', '\n').strip()
    c = COMPANY
    if cfg['name'] == 'SPIN':
        if lang == 'EN':
            lines = [f"spin.clinic · {c['name']} (operator of spin.clinic and przeszłość.today)",
                     f"{c['street']}, {c['city']}, Poland · KRS {c['krs']} · VAT PL{c['nip']}",
                     f"{cfg['address']} · https://spin.clinic"]
        else:
            lines = [f"spin.clinic · {c['name']} (operator serwisów spin.clinic i przeszłość.today)",
                     f"{c['street']}, {c['city']} · KRS {c['krs']} · NIP {c['nip']} · REGON {c['regon']}",
                     f"{cfg['address']} · https://spin.clinic"]
    else:
        lines = [c['name'], f"{c['street']}, {c['city']}" + (', Poland' if lang == 'EN' else ''),
                 f"KRS {c['krs']} · NIP {c['nip']} · REGON {c['regon']}",
                 (f"{c['court']} · kapitał zakładowy {c['capital']}" if lang == 'PL'
                  else f"District Court Poznań - Nowe Miasto i Wilda in Poznań, 8th Commercial Division (KRS) · share capital PLN 50,000"),
                 f"{cfg['address']} · https://iapply.pl"]
    return '\n\n-- \n' + '\n'.join(lines)


def footer_from_sent(cfg):
    """Ostatnia wiadomość z folderu Wysłane skrzynki: temat, data i blok stopki (po „-- ” albo po zwrocie grzecznościowym).
    Służy do skopiowania prawdziwego formatu stopki właściciela do szablonu. Tylko odczyt."""
    client = _connect(cfg)
    try:
        folder = sent_folder(client)
        client.select(_quote(folder), readonly=True)
        status, data = client.uid('search', None, 'ALL')
        uids = data[0].split() if status == 'OK' and data and data[0] else []
        if not uids:
            return {'folder': folder, 'subject': '', 'date': '', 'footer': '', 'note': 'folder Wysłane jest pusty'}
        raw = poczta._fetch_raw(client, int(uids[-1]))
        message = message_from_bytes(raw or b'', policy=policy.default)
        text = poczta._text(message)
        return {'folder': folder, 'subject': poczta._header(message, 'Subject'), 'date': poczta._header(message, 'Date'),
                'footer': extract_footer(text), 'note': ''}
    finally:
        _logout(client)


def extract_footer(text):
    text = (text or '').replace('\r\n', '\n').strip()
    if '\n-- \n' in text:
        return text.rsplit('\n-- \n', 1)[1].strip()
    lines = text.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        if CLOSINGS.match(lines[i].strip()):
            return '\n'.join(lines[i:]).strip()
    tail = [l for l in lines if l.strip()][-8:]
    return '\n'.join(tail).strip()


# --- kontrola Recenzenta i Prawnika ----------------------------------------------------------------------------------------

def own_domains():
    return tuple(set(poczta.allowed_domains()) | {'iapply.pl'})


def check_item(item, cfg) -> list[str]:
    """Zarzuty do listu (pusta lista = można wysłać). Reguły stałe, bez modelu i bez sieci."""
    problems = list(item['problems'])
    body = item['body']
    if PLACEHOLDER in body and not signer():
        problems.append('brak MAIL_OUTBOX_SIGNER (imię i nazwisko, funkcja osoby uprawnionej) dla miejsca {{PODPIS}}')
    for hit in BRACKETS.findall(body)[:2]:
        problems.append(f'miejsce do uzupełnienia: {hit[:50]}')
    if '—' in body or '–' in body:
        problems.append('długa kreska')
    if len(body) < 80:
        problems.append('za krótki')
    if len(body) > 12000:
        problems.append('za długi')
    if item['lang'] == 'PL':
        words = {w.strip('.,!?:;„”"()').lower() for w in body.split()}
        if len(words & poczta.POLISH_WORDS) < 2 and not re.search(r'[ąćęłńóśźż]', body, re.I):
            problems.append('nie po polsku (ustaw lang: EN, jeśli list jest po angielsku)')
    hit = COLD_OFFER.search(body)
    if hit and item['category'] != 'odpowiedz':
        problems.append(f'oferta handlowa przy pierwszym kontakcie (PKE art. 398): „{hit.group(0)}”')
    hit = PROMISES.search(body)
    if hit:
        problems.append(f'obietnica pieniędzy: „{hit.group(0)}”')
    masked = IDENTIFIERS.sub(' ', body)
    allowed = own_domains()
    for address in set(poczta.EMAIL_RE.findall(masked)):
        domain = address.rsplit('@', 1)[-1].lower()
        if address.lower() != item['to'] and not any(domain == d or domain.endswith('.' + d) for d in allowed):
            problems.append(f'adres e-mail osoby trzeciej: {address}')
    if poczta.PHONE_RE.search(masked):
        problems.append('numer telefonu w treści')
    if poczta.PESEL_RE.search(re.sub(r'\d+\.\d+\.\d+\.\d+', ' ', masked)):
        problems.append('ciąg 11 cyfr (PESEL?)')
    if UNPROFESSIONAL.search(body) or SHOUTING.search(body):
        problems.append('ton: wykrzykniki, wersaliki albo emoji')
    for name in item['attachments']:
        if not (Path(item['path']).parent / name).is_file():
            problems.append(f'brak załącznika: {name}')
    return problems


# --- IMAP: folder Wysłane (duplikaty, kopia) ------------------------------------------------------------------------------

def _connect(cfg):
    import ssl
    client = poczta.imaplib.IMAP4_SSL(cfg['imap_host'], cfg['imap_port'], ssl_context=ssl.create_default_context())
    client.login(cfg['imap_user'], cfg['imap_password'])
    return client


def _logout(client):
    try:
        client.logout()
    except Exception:  # noqa: BLE001
        pass


def _quote(folder):
    return f'"{folder}"' if ' ' in folder and not folder.startswith('"') else folder


def _folder_name(line):
    text = line.decode(errors='replace') if isinstance(line, (bytes, bytearray)) else str(line)
    match = re.match(r'^\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$', text.strip())
    if not match:
        return '', ''
    return match.group('flags'), match.group('name').strip().strip('"')


def sent_folder(client):
    status, rows = client.list()
    for row in rows or []:
        flags, name = _folder_name(row)
        if name and '\\sent' in flags.lower():
            return name
    names = {_folder_name(r)[1] for r in rows or []}
    for candidate in SENT_FOLDERS:
        if candidate in names:
            return candidate
    for candidate in SENT_FOLDERS:
        try:
            status, _ = client.select(_quote(candidate), readonly=True)
        except poczta.imaplib.IMAP4.error:
            continue
        if status == 'OK':
            return candidate
    raise poczta.MailboxError('sent_folder_missing')


def similar(a, b):
    a, b = poczta.normalized_subject(a), poczta.normalized_subject(b)
    if not a or not b:
        return False
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= SIMILARITY


def _since(now):
    day = (now - timedelta(days=DUPLICATE_DAYS)).astimezone(poczta.WARSAW)
    return f'{day.day:02d}-{MONTHS[day.month - 1]}-{day.year}'


def already_sent(client, folder, address, subject, now):
    """(czy w folderze Wysłane jest list do tego adresu o podobnym temacie z ostatnich 60 dni, jego data i temat)."""
    status, _ = client.select(_quote(folder), readonly=True)
    if status != 'OK':
        raise poczta.MailboxError('sent_folder_unavailable')
    status, data = client.uid('search', None, f'SINCE {_since(now)}', f'TO "{address}"')
    uids = data[0].split() if status == 'OK' and data and data[0] else []
    for uid in uids[-SENT_SCAN:]:
        status, result = client.uid('fetch', uid.decode() if isinstance(uid, bytes) else str(uid), '(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE TO)])')
        if status != 'OK':
            continue
        for part in result or []:
            if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
                header = message_from_bytes(bytes(part[1]), policy=policy.default)
                found = poczta._header(header, 'Subject')
                if similar(found, subject):
                    return True, poczta._header(header, 'Date'), found
    return False, '', ''


def append_sent(client, folder, email):
    try:
        status, _ = client.append(_quote(folder), '\\Seen', poczta.imaplib.Time2Internaldate(time.time()), email.as_bytes())
        return status == 'OK'
    except (OSError, poczta.imaplib.IMAP4.error) as error:
        logger.warning('poczta wychodząca: append failed (%s)', type(error).__name__)
        return False


# --- budowa i wysyłka -------------------------------------------------------------------------------------------------------

def build_message(item, cfg, parent: MailOutboxLog | None = None):
    body = item['body'].replace(PLACEHOLDER, signer())
    email = EmailMessage()
    email['From'] = cfg['smtp_from']
    email['To'] = item['to']
    email['Subject'] = item['subject'] if not parent else poczta._reply_subject(item['subject'])
    domain = cfg['address'].split('@', 1)[1] if '@' in cfg['address'] else None
    email['Message-ID'] = make_msgid(domain=domain)
    if parent and parent.message_id:
        email['In-Reply-To'] = parent.message_id
        email['References'] = parent.message_id
    email.set_content(body + signature(cfg, item['lang']))
    for name in item['attachments']:
        path = Path(item['path']).parent / name
        ctype, _ = mimetypes.guess_type(name)
        maintype, subtype = (ctype or 'application/octet-stream').split('/', 1)
        email.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=name)
    return email


def sent_today(mailbox, now):
    return MailOutboxLog.objects.filter(mailbox=mailbox, status='sent', sent_at__gte=poczta.day_start(now)).count()


def _log(item, cfg, status, reason='', message_id='', copy_saved=False, now=None):
    """Wpis rejestru; zatrzymania i duplikaty z tym samym powodem nie są powtarzane (jeden wpis na stan)."""
    if status in ('blocked', 'duplicate') and MailOutboxLog.objects.filter(key=item['key'], status=status, reason=reason[:300]).exists():
        return None
    return MailOutboxLog.objects.create(key=item['key'], mailbox=cfg['name'], recipient=item['to'], subject=item['subject'][:500],
                                        category=item['category'] if item['category'] in CATEGORY_KEYS else '', status=status,
                                        reason=reason[:300], message_id=message_id[:512], copy_saved=copy_saved,
                                        sent_at=now if status == 'sent' else None)


def run(plan=True, now=None, directory: Path | None = None):
    """Przegląd kolejki: dla każdego listu decyzja i (gdy plan=False) wysyłka. Zwraca listę wierszy
    {key, mailbox, to, subject, action: send|sent|skip|block|failed, reason}."""
    now = now or timezone.now()
    today = now.astimezone(poczta.WARSAW).date()
    rows, clients, folders, sent_now = [], {}, {}, {}
    configured = set(poczta.names())
    try:
        for item in load_items(directory):
            row = {'key': item['key'], 'mailbox': item['mailbox'], 'to': item['to'], 'subject': item['subject'][:120],
                   'category': item['category'], 'action': 'skip', 'reason': ''}
            rows.append(row)
            cfg = poczta.config(item['mailbox']) if item['mailbox'] in configured else None
            if item['problems']:
                row.update(action='block', reason='plik: ' + '; '.join(item['problems']))
                continue
            if item['hold']:
                row['reason'] = 'wstrzymany: ' + item['hold']
                continue
            if item['not_before'] and item['not_before'] > today:
                row['reason'] = f"czeka do {item['not_before']:%d.%m}"
                continue
            if not item['to']:
                row['reason'] = 'brak adresu e-mail' + (f" (adres ze strony: {item['contact_url']})" if item['contact_url'] else '')
                continue
            if cfg is None:
                row.update(action='block', reason=f"skrzynka {item['mailbox']} nie jest w MAILBOXES")
                continue
            if not poczta.smtp_ready(cfg) or not poczta.imap_ready(cfg):
                row.update(action='block', reason='brak zmiennych: ' + ', '.join(poczta.missing(item['mailbox'])))
                continue
            problems = check_item(item, cfg)
            if problems:
                row.update(action='block', reason='kontrola: ' + '; '.join(problems))
                if not plan:
                    _log(item, cfg, 'blocked', row['reason'], now=now)
                continue
            previous = MailOutboxLog.objects.filter(key=item['key'], status='sent').order_by('-sent_at').first()
            if previous:
                row['reason'] = f"już wysłane {previous.sent_at.astimezone(poczta.WARSAW):%d.%m} (rejestr)"
                continue
            parent = None
            if item['reply_to_item']:
                parent = MailOutboxLog.objects.filter(key=item['reply_to_item'], status='sent').order_by('-sent_at').first()
                if parent is None:
                    row.update(action='block', reason=f"w wątku listu {item['reply_to_item']}, który jeszcze nie wyszedł")
                    continue
            if sent_today(cfg['name'], now) + sent_now.get(cfg['name'], 0) >= daily_limit():
                row['reason'] = f'limit dzienny {daily_limit()} na skrzynkę'
                continue
            try:
                if cfg['name'] not in clients:
                    clients[cfg['name']] = _connect(cfg)
                    folders[cfg['name']] = sent_folder(clients[cfg['name']])
                duplicate, when, found = already_sent(clients[cfg['name']], folders[cfg['name']], item['to'], item['subject'], now)
            except (OSError, poczta.imaplib.IMAP4.error, poczta.MailboxError) as error:
                clients.pop(cfg['name'], None)
                row.update(action='block', reason=f'bez kontroli duplikatów nie wysyłam (IMAP: {type(error).__name__})')
                continue
            if duplicate:
                row['reason'] = f"już w Wysłane ({when[:16] or 'data nieznana'}): {found[:60]}"
                if not plan:
                    _log(item, cfg, 'duplicate', row['reason'], now=now)
                continue
            if plan:
                row.update(action='send', reason='do wysłania')
                continue
            email = build_message(item, cfg, parent)
            try:
                message_id = poczta.deliver(email, cfg)
            except (OSError, poczta.smtplib.SMTPException) as error:
                row.update(action='failed', reason='SMTP: ' + type(error).__name__)
                _log(item, cfg, 'failed', row['reason'], now=now)
                continue
            copied = append_sent(clients[cfg['name']], folders[cfg['name']], email)
            sent_now[cfg['name']] = sent_now.get(cfg['name'], 0) + 1
            row.update(action='sent', reason='wysłano' + ('' if copied else ' (bez kopii w Wysłane)'))
            _log(item, cfg, 'sent', row['reason'], message_id=message_id or '', copy_saved=copied, now=now)
    finally:
        for client in clients.values():
            _logout(client)
    return rows


# --- zestawienie 7:10 ------------------------------------------------------------------------------------------------------

STATUS_LABELS = {'sent': 'wysłano', 'failed': 'błąd wysyłki', 'blocked': 'zatrzymane', 'duplicate': 'pominięte (duplikat)'}


def digest_lines(rows):
    lines = ['Poczta wychodząca - kolejka listów (deploy/poczta-wychodzaca):']
    for row in rows:
        label = poczta.config(row.mailbox)['label'] if row.mailbox in poczta.names() else row.mailbox
        when = row.sent_at or row.created_at
        lines.append(f"- [{label}] {STATUS_LABELS.get(row.status, row.status)} {when.astimezone(poczta.WARSAW):%d.%m %H:%M} · "
                     f"do {row.recipient or '(brak adresu)'} · {row.subject or '(bez tematu)'}" + (f' · {row.reason}' if row.reason and row.status != 'sent' else ''))
    lines.append('Plan kolejki: python manage.py poczta --wyslij-kolejke --plan')
    return lines


def format_rows(rows, plan=True):
    """Czytelny wydruk planu albo wyniku dla komendy i raportu."""
    if not rows:
        return [f'Kolejka pusta: brak plików *.md w {outbox_dir()}']
    order = {'send': 0, 'sent': 0, 'failed': 1, 'block': 2, 'skip': 3}
    lines = []
    for row in sorted(rows, key=lambda r: (order.get(r['action'], 9), r['key'])):
        mark = {'send': 'WYŚLE', 'sent': 'WYSŁANO', 'failed': 'BŁĄD', 'block': 'STOP', 'skip': 'POMIJA'}[row['action']]
        lines.append(f"{mark:8}[{row['mailbox'] or '?'}] {row['key']} -> {row['to'] or '(brak adresu)'} · {row['subject'] or '(bez tematu)'}")
        if row['reason']:
            lines.append(f"         {row['reason']}")
    counts = {k: sum(1 for r in rows if r['action'] == k) for k in ('send', 'sent', 'failed', 'block', 'skip')}
    if plan:
        lines.append(f"Plan: do wysłania {counts['send']}, zatrzymane {counts['block']}, pominięte {counts['skip']}. Nic nie wysłano.")
    else:
        lines.append(f"Wynik: wysłano {counts['sent']}, błędy {counts['failed']}, zatrzymane {counts['block']}, pominięte {counts['skip']}.")
    return lines
