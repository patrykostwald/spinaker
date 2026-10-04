"""Pełny audyt od razu (właściciel 5.10): Recenzent (treści z 14 dni i stałe teksty stron) oraz Projektant (wiedza i wygląd).
Każdy krok osobno: brak limitu u jednego modelu nie zatrzymuje pozostałych."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news import projektant, recenzent


class Command(BaseCommand):
    help = 'Recenzja treści z 14 dni, audyt stałych tekstów wszystkich stron i przegląd UX/UI (wyniki w panelu Agenci i mailem).'

    def handle(self, *args, **opts):
        steps = [
            ('Recenzent: treści z 14 dni', lambda: recenzent.step(force=True, items=recenzent.collect(timezone.now() - timedelta(days=14)))),
            ('Recenzent: stałe teksty stron', lambda: recenzent.audit_pages(force=True)),
            ('Projektant: wiedza z branży', lambda: projektant.learn(force=True)),
            ('Projektant: wygląd stron', lambda: projektant.audit(force=True)),
        ]
        for name, run in steps:
            try:
                note = run()
            except Exception as error:  # noqa: BLE001 - krok nieudany, kolejne działają dalej
                self.stdout.write(self.style.WARNING(f'{name}: nie udało się ({str(error)[:200]}). Spróbuj ponownie po odnowieniu limitów.'))
                continue
            self.stdout.write(self.style.SUCCESS(f'{name}: {note.title if note else "brak nowych tekstów"}'))
            if note:
                self.stdout.write(note.body[:4000] + '\n')
