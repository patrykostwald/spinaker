"""Poczta (właściciel 6.10) od ręki.

python manage.py poczta --stan   - skrzynki z MAILBOXES: komplet zmiennych (nazwy brakujących), ostatni odczyt i błąd, liczby, wyłącznik wysyłki
python manage.py poczta --plan   - próba na ostatnich 20 wiadomościach każdej skrzynki: kategoria, decyzja i szkic; bez zapisu i bez wysyłki
python manage.py poczta --raz    - jeden przebieg jak zadanie co 10 minut (wysyłka tylko przy MAIL_AGENT_AUTOSEND=true)
python manage.py poczta --zestawienie - zestawienie do właściciela teraz (wiadomości bez automatycznej odpowiedzi)"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Poczta: stan skrzynek, próba na ostatnich wiadomościach, jeden przebieg, zestawienie.'

    def add_arguments(self, parser):
        parser.add_argument('--stan', action='store_true')
        parser.add_argument('--plan', action='store_true')
        parser.add_argument('--raz', action='store_true')
        parser.add_argument('--zestawienie', action='store_true')
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        from news import poczta
        out = self.stdout.write
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
