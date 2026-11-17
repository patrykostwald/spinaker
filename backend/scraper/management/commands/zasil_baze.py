"""Zasilanie bazy: plan (bez sieci) albo ręczna porcja historii jednego źródła lub pasa.

  manage.py zasil_baze --plan                       co brakuje, ile zapytań i dni do końca (bez sieci)
  manage.py zasil_baze --zrodlo votes --limit 100   porcja historii jednego źródła (te same karty i odstępy)
  manage.py zasil_baze --zrodlo sejm --limit 40     porcja każdego niegotowego źródła z pasa (sejm / inne)
  manage.py zasil_baze --zrodlo ted --dni 365       okno historii w dniach (źródła z oknem: TED; Sejm od 13.11.2023)
"""
import json

from django.core.management.base import BaseCommand, CommandError

from scraper import zasil_baze as zb


class Command(BaseCommand):
    help = 'Zasilanie bazy historią włączonych źródeł: --plan albo porcja --zrodlo (wznawialne, w limitach kart).'

    def add_arguments(self, parser):
        parser.add_argument('--plan', action='store_true')
        parser.add_argument('--zrodlo', help='źródło (np. votes, ted) albo pas: ' + ', '.join(zb.LANES))
        parser.add_argument('--dni', type=int, help='okno historii w dniach (zamiast domyślnego)')
        parser.add_argument('--limit', type=int, default=20, help='najwyżej tyle zapytań na źródło (1-2000)')
        parser.add_argument('--tryb', choices=tuple(zb.MODES), default='noc')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        if options['plan'] or not options['zrodlo']:
            return self.plan(options['json'])
        name, limit = options['zrodlo'], options['limit']
        if not 1 <= limit <= 2000:
            raise CommandError('--limit: 1-2000.')
        if options['dni'] is not None and not 1 <= options['dni'] <= 1095:
            raise CommandError('--dni: 1-1095.')
        sources = zb.LANES.get(name) or ((name,) if name in zb.SOURCES else None)
        if not sources:
            raise CommandError('Nieznane źródło. Dostępne: ' + ', '.join(list(zb.LANES) + list(zb.SOURCES)))
        out = {}
        for source in sources:
            used, added, last = 0, 0, {}
            while used < limit:
                last = zb.run_source(source, options['tryb'], max_requests=min(20, limit - used), days=options['dni'])
                used += max(1, last.get('requests') or 0)
                added += max(0, last.get('added', 0))
                if not last.get('completed') or last.get('complete'):
                    break
            out[source] = {'status': last.get('status'), 'added': added, 'complete': zb.complete(source),
                           **({'error': last['error']} if last.get('error') else {})}
        links = zb.link_after('sejm') if any(v['added'] for v in out.values()) else None
        self.stdout.write(json.dumps({'sources': out, 'links': links}, ensure_ascii=False))

    def plan(self, as_json):
        rows = zb.plan()
        links = zb.links_summary()
        if as_json:
            self.stdout.write(json.dumps({'sources': rows, 'links': links}, ensure_ascii=False, default=str))
            return
        self.stdout.write('Zasilanie bazy - plan (szacunek; dni = doby przy obecnych kartach i limitach)')
        self.stdout.write(f"{'źródło':<16}{'flaga':<6}{'karta':>7}{'limit':>7}{'od':>12}{'rekordy':>9}{'24 h':>7}"
                          f"{'kolejka':>9}{'zostało':>9}{'%':>5}{'dni':>6}  stan")
        for r in rows:
            days = '-' if r['days'] is None else str(r['days'])
            card = '-' if r['card_cap'] is None else str(r['card_cap'])
            limit = '-' if r['backfill_cap'] is None else str(r['backfill_cap'])
            records = '-' if r['records'] is None else str(r['records'])
            added = '-' if r['added_24h'] is None else str(r['added_24h'])
            state = 'gotowe' if r['percent'] == 100 else r['status'] + (f" ({r['error']})" if r['error'] else '')
            self.stdout.write(f"{r['source']:<16}{('tak' if r['enabled'] else 'nie'):<6}{card:>7}{limit:>7}"
                              f"{r['target']:>12}{records:>9}{added:>7}{r['pending']:>9}{r['remaining']:>9}"
                              f"{r['percent']:>5}{days:>6}  {state}")
            if r.get('note'):
                self.stdout.write('  ! ' + r['note'])
            if r['enabled'] and r['card_cap'] == 0:
                self.stdout.write('  ! brak ważnej karty dostępu: deploy/zasil-baze.sh')
            elif r['enabled'] and r['card_cap'] and r['backfill_cap'] and r['card_cap'] < r['backfill_cap']:
                self.stdout.write(f"  ! karta {r['card_cap']}/dobę mniejsza niż limit zasilania - deploy/zasil-baze.sh")
        self.stdout.write(f"Powiązania z osobami: {links['linked']} z {links['total']} (bez osoby: {links['unlinked']})")
