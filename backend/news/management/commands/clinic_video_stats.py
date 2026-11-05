"""Prywatne zestawienie filmów z wpisów polityków."""
import json

from django.core.management.base import BaseCommand

from news.clinic_video_stats import build_report, format_report


class Command(BaseCommand):
    help = 'Filmy rządzących i opozycji: wczoraj, 7 dni, koszty i równowaga oglądania.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='Wynik w formacie JSON.')

    def handle(self, **options):
        report = build_report()
        self.stdout.write(json.dumps(report, ensure_ascii=False) if options['json'] else format_report(report))
