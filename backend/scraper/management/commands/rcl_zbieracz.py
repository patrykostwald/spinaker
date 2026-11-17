"""Zbieracz Rządowego Procesu Legislacyjnego: ręczne uruchomienie, rozpoznanie, status i tryb offline.

  manage.py rcl_zbieracz --status                     stan: flaga, okno, wstrzymanie, karta, liczby rekordów (bez sieci)
  manage.py rcl_zbieracz --dry-run                    przebieg na plikach testowych, w transakcji wycofywanej (bez sieci)
  manage.py rcl_zbieracz --rozpoznanie --zrzut DIR    pierwsza noc: robots, po 1 stronie listy każdego rodzaju i 4 projekty,
                                                      najwyżej 30 zapytań, surowe strony do DIR
  manage.py rcl_zbieracz                              porcja nocna (jak zadanie Celery); poza oknem 01:00-06:00 nic nie wysyła
"""
import json

from django.core.management.base import BaseCommand, CommandError

from news.models import (ImportState, LegislativeChange, LegislativeDocument, LegislativeProject, LegislativeStage,
                         RclFetchEvent)
from scraper import rcl_guard, rcl_harvest


def status():
    source, card = rcl_harvest.configured_access()
    until = rcl_guard.halted_until()
    last = ImportState.objects.filter(name='rcl:last-run').first()
    night = ImportState.objects.filter(name='rcl:night').first()
    return {
        'RCL_FETCH_ENABLED': rcl_guard.fetch_enabled(),
        'window_open_now': rcl_guard.window_open(allowance_seconds=rcl_guard.REQUEST_ALLOWANCE_SECONDS),
        'now_warsaw': rcl_guard.local_now().isoformat(timespec='seconds'),
        'halted_until': until.isoformat() if until else None,
        'source_configured': source is not None,
        'access_card_valid': card is not None,
        'nightly_budget': rcl_harvest.nightly_budget(),
        'night_usage': (night.cursor if night else None),
        'types': list(rcl_harvest.type_ids()),
        'robots_override': rcl_harvest.robots_override(),
        'files_enabled': rcl_harvest.files_enabled(),
        'projects': LegislativeProject.objects.count(),
        'projects_waiting': LegislativeProject.objects.filter(needs_refresh=True).count(),
        'stages': LegislativeStage.objects.count(),
        'documents': LegislativeDocument.objects.count(),
        'changes': LegislativeChange.objects.count(),
        'last_events': list(RclFetchEvent.objects.values('created_at', 'kind', 'http_status')[:5]),
        'last_run': (last.cursor if last else None),
    }


class Command(BaseCommand):
    help = 'Zbieracz RCL (legislacja.rcl.gov.pl) pod warunkami z pisma RCL.DPK.053.168.2026; pobiera tylko w oknie 01:00-06:00.'

    def add_arguments(self, parser):
        parser.add_argument('--status', action='store_true')
        parser.add_argument('--dry-run', action='store_true', help='Na plikach testowych, bez sieci, z wycofaniem zapisów.')
        parser.add_argument('--rozpoznanie', action='store_true', help='Pierwsza noc: najwyżej 30 zapytań i zrzut stron.')
        parser.add_argument('--zrzut', help='Katalog na surowe strony (tylko z --rozpoznanie), poza repozytorium.')
        parser.add_argument('--limit-zapytan', type=int, help='Budżet zapytań tej porcji (domyślnie RCL_NIGHTLY_REQUEST_BUDGET).')
        parser.add_argument('--sekundy', type=int, help='Najdłuższy czas porcji w sekundach.')

    def handle(self, *args, **options):
        if options['status']:
            return self.out(status())
        if options['dry_run']:
            return self.out(rcl_harvest.dry_run())
        limit = options['limit_zapytan']
        if limit is not None and not 1 <= limit <= 3600:
            raise CommandError('--limit-zapytan: 1-3600.')
        recon = options['rozpoznanie']
        if recon:
            limit = min(limit or 30, 30)
        elif options['zrzut']:
            raise CommandError('--zrzut wymaga --rozpoznanie.')
        self.out(rcl_harvest.run_night(recon=recon, budget=limit, seconds=options['sekundy'], dump_dir=options['zrzut']))

    def out(self, data):
        self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
