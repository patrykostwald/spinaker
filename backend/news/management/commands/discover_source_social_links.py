"""Szuka na stronach głównych źródeł linków do ich kanału YouTube i konta X (dowód: strona źródła).

Bez --apply zapisuje tylko dowody (co znaleziono na stronie). Z --apply ustala identyfikatory kanałów
YouTube (1 jednostka darmowego limitu na kanał) i dodaje je do przeglądu jako pending_review. Nic nie
pobiera z kanałów i niczego nie potwierdza — to robi confirm_source_youtube_channels.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news import source_social, youtube_collect
from news.management.commands.seed_official_youtube_channels import resolve
from news.management.commands.source_access_report import kind
from news.models import Source
from news.political_models import OfficialVideoChannel


class Command(BaseCommand):
    help = 'Linki YouTube i X ze stron głównych źródeł (robots.txt, 3 s na host). --apply: kanały YouTube do przeglądu.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=60)
        parser.add_argument('--force', action='store_true', help='Sprawdź ponownie także źródła sprawdzone w ostatnich 30 dniach.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, limit, force, apply, **options):
        from scraper.source_probe import ProbeNetwork
        network = ProbeNetwork(delay=3)
        sources = (Source.objects.exclude(catalog_stage='excluded').exclude(url__isnull=True).exclude(url='')
                   .exclude(url__contains='youtube.com').order_by('pk'))
        checked = found = queued = 0
        for source in sources:
            if checked >= limit:
                break
            previous = source_social.stored(source)
            when = parse_datetime(previous.get('checked_at') or '')
            if (not force and when and when >= timezone.now() - timedelta(days=30)
                    and previous.get('version') == source_social.VERSION):
                result = previous
            else:
                result = source_social.discover(source, network)
                checked += 1
            host = source.url.split('/')[2] if '//' in source.url else ''
            if result.get('youtube') or result.get('x'):
                found += 1
                self.stdout.write(f"{source.pk}|{kind(host)}|{source.name[:50]}|YT: {' '.join(result['youtube']) or '-'}|X: {' '.join('@' + h for h in result['x']) or '-'}")
            if apply and result.get('youtube') and youtube_collect.enabled():
                queued += self.queue(source, result)
        self.stdout.write(f'Sprawdzono teraz: {checked}; źródeł z linkami: {found}; kanałów YouTube do przeglądu: {queued}')

    def queue(self, source, result) -> int:
        added = 0
        source_type = ContentType.objects.get_for_model(Source)
        for link in result['youtube'][:1]:  # pierwszy link ze strony — zwykle kanał w stopce
            try:
                channel_id, title = resolve(link)
            except youtube_collect.QuotaExhausted:
                return added
            if not channel_id or OfficialVideoChannel.objects.filter(channel_id=channel_id).exists():
                continue
            row = OfficialVideoChannel(subject_content_type=source_type, subject_object_id=source.pk,
                                       channel_url=f'https://www.youtube.com/channel/{channel_id}', channel_id=channel_id,
                                       display_name=source.name[:255], evidence_url=result['evidence_url'], status='pending_review')
            row.full_clean()
            row.save()
            added += 1
            self.stdout.write(f'  → do przeglądu: {source.name} — {title} ({channel_id})')
        return added
