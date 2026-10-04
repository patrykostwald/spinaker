"""Pełny audyt od razu (właściciel 5.10): Recenzent czyta treści z 14 dni, Projektant uczy się z branży i przegląda wszystkie strony."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news import projektant, recenzent


class Command(BaseCommand):
    help = 'Recenzja treści z 14 dni, audyt stałych tekstów wszystkich stron (językoznawca, dziennikarz, rzetelność, czytelnik) i przegląd UX/UI (wyniki w panelu Agenci i mailem).'

    def handle(self, *args, **opts):
        note = recenzent.step(force=True, items=recenzent.collect(timezone.now() - timedelta(days=14)))
        self.stdout.write(note.title if note else 'Recenzent: brak nowych tekstów.')
        pages = recenzent.audit_pages(force=True)
        self.stdout.write(pages.title)
        self.stdout.write(pages.body[:6000])
        self.stdout.write(projektant.learn(force=True).title)
        audit = projektant.audit(force=True)
        self.stdout.write(audit.title)
        self.stdout.write(audit.body[:4000])
