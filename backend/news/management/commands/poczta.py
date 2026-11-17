"""Poczta (właściciel 6.10) od ręki.

python manage.py poczta --stan   - skrzynki z MAILBOXES: komplet zmiennych (nazwy brakujących), ostatni odczyt i błąd, liczby, wyłącznik wysyłki
python manage.py poczta --plan   - próba na ostatnich 20 wiadomościach każdej skrzynki: kategoria, decyzja i szkic; bez zapisu i bez wysyłki
python manage.py poczta --raz    - jeden przebieg jak zadanie co 10 minut (wysyłka tylko przy MAIL_AGENT_AUTOSEND=true)
python manage.py poczta --zestawienie - zestawienie do właściciela teraz (wiadomości bez automatycznej odpowiedzi)
python manage.py poczta --wyslij-kolejke --plan - kolejka listów (deploy/poczta-wychodzaca): co by poszło i dlaczego nie; nic nie wysyła
python manage.py poczta --wyslij-kolejke        - wysyłka kolejki (kontrola, duplikaty z folderu Wysłane, limit dzienny, kopia w Wysłane, rejestr)
python manage.py poczta --podpis PATRYK         - stopka z ostatniej wiadomości w folderze Wysłane tej skrzynki (do skopiowania do szablonu)"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Poczta: stan skrzynek, próba na ostatnich wiadomościach, jeden przebieg, zestawienie, kolejka wychodząca, stopka.'

    def add_arguments(self, parser):
        parser.add_argument('--stan', action='store_true')
        parser.add_argument('--plan', action='store_true')
        parser.add_argument('--raz', action='store_true')
        parser.add_argument('--zestawienie', action='store_true')
        parser.add_argument('--wyslij-kolejke', action='store_true', dest='kolejka')
        parser.add_argument('--podpis', metavar='SKRZYNKA')
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        from news import poczta
        out = self.stdout.write
        if options['kolejka']:
            from news import poczta_wychodzaca
            rows = poczta_wychodzaca.run(plan=options['plan'])
            out(f"Kolejka: {poczta_wychodzaca.outbox_dir()} · limit dzienny na skrzynkę: {poczta_wychodzaca.daily_limit()} · "
                f"podpis osoby uprawnionej (MAIL_OUTBOX_SIGNER): {'jest' if poczta_wychodzaca.signer() else 'brak'}")
            for line in poczta_wychodzaca.format_rows(rows, plan=options['plan']):
                out(line)
            return
        if options['podpis']:
            from news import poczta_wychodzaca
            name = options['podpis'].strip().upper()
            if name not in poczta.names():
                out(f"Skrzynka {name} nie jest w MAILBOXES ({', '.join(poczta.names()) or 'puste'}).")
                return
            cfg = poczta.config(name)
            if not poczta.imap_ready(cfg):
                out('Brak zmiennych: ' + ', '.join(poczta.missing(name, poczta.IMAP_KEYS)))
                return
            try:
                found = poczta_wychodzaca.footer_from_sent(cfg)
            except (OSError, poczta.imaplib.IMAP4.error, poczta.MailboxError) as error:
                out(f'IMAP: {type(error).__name__}')
                return
            out(f"Folder: {found['folder']} · ostatnia wiadomość: {found['subject'] or '(bez tematu)'} · {found['date']}")
            out(found['note'] or 'Stopka znaleziona w ostatniej wiadomości:')
            for line in found['footer'].splitlines():
                out('   ' + line)
            out(f"Szablon domyślny tej skrzynki:{poczta_wychodzaca.signature(cfg)}")
            out(f"Własna stopka: zmienna {poczta.env_name(name, 'SIGNATURE')} (literalne \\n to nowa linia).")
            return
        if options['plan']:
            rows = poczta.plan(limit=max(1, min(options['limit'], 50)))
            if not rows:
                out('Brak skrzynek: ustaw MAILBOXES i zmienne MAILBOX_<NAZWA>_IMAP_HOST/USER/PASSWORD.')
            for row in rows:
                if row.get('error'):
                    out(f"[{row['mailbox']}] {row['error']}")
                    continue
                out(f"[{row['mailbox']}] #{row['uid']} od {row['from'] or '(brak)'} · {row['subject'] or '(bez tematu)'}")
                out(f"   kategoria: {row['category'] or 'brak'} ({row['confidence']}) · {row['reason']} · model: {row['model'] or '-'}")
                out(f"   decyzja: {row['action']}" + (f" - {row['why']}" if row['why'] else '') + (f" · zarzuty: {', '.join(row['checks'])}" if row['checks'] else ''))
                if row['reply']:
                    out('   szkic:')
                    out('\n'.join('      ' + l for l in row['reply'].splitlines() if l.strip()))
            out(f"Wysyłka automatyczna: {'włączona' if poczta.autosend() else 'wyłączona (MAIL_AGENT_AUTOSEND=true włącza)'}; nic nie wysłano.")
            return
        if options['raz']:
            out(str(poczta.run()))
            return
        if options['zestawienie']:
            out(str(poczta.digest()))
            return
        state = poczta.stan()
        out(f"Poczta: {'włączona' if state['enabled'] else 'wyłączona'} · wysyłka automatyczna: {'włączona' if state['autosend'] else 'wyłączona (MAIL_AGENT_AUTOSEND)'}"
            f" · limit dzienny na skrzynkę: {state['daily_limit']}")
        if state['missing_global']:
            out('Brak zmiennych: ' + ', '.join(state['missing_global']) + ' (np. MAILBOXES=SPIN,PRZESZLOSC,ZBUDUJMI,IAPPLY)')
        for box in state['mailboxes']:
            ok = 'IMAP ok' if box['imap'] else 'IMAP wyłączone'
            smtp = 'SMTP ok' if box['smtp'] else 'SMTP brak (tylko odczyt i zestawienie)'
            out(f"- {box['label']} ({box['name']}): {ok}, {smtp}; wiadomości: {box['messages']}, czeka: {box['waiting']}, "
                f"odpowiedzi dziś: {box['replied_today']}, do zestawienia: {box['escalated_open']}, ostatni UID: {box['last_uid']}")
            if box['last_ok_at']:
                out(f"   ostatni udany odczyt: {box['last_ok_at']:%d.%m %H:%M}")
            if box['last_error']:
                out(f"   ostatni błąd: {box['last_error']} ({box['last_error_at']:%d.%m %H:%M})")
            if box['missing']:
                out('   brak zmiennych: ' + ', '.join(box['missing']))
        c = state['counts_24h']
        out(f"24 h: odebrane {c['received']}, odpowiedziane {c['replied']}, do właściciela {c['escalated']}, pominięte {c['skipped']}, czeka {c['waiting']}")
