"""Bulk implementation of the owner's 3 October 2026 metadata decision."""
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from scraper import public_institution_approval as approval


class Command(BaseCommand):
    help = 'Zatwierdza instytucje publiczne wyłącznie na metadane. Domyślnie podgląd bez zapisów.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Zapisuje karty i włącza potwierdzone źródła.')

    def handle(self, *args, **options):
        apply = options['apply']
        approved, skipped = [], defaultdict(list)
        network = approval.ApprovalProbeNetwork()
        self.stdout.write('ZAPIS' if apply else 'PODGLĄD: bez zapisów; możliwa jedna próba kanału na źródło.')
        for source in Source.objects.order_by('name', 'pk').iterator():
            label = f'{source.name} (id={source.pk})'
            cards = list(source.access_instructions.order_by('-version'))
            reason = approval.eligibility(source, cards)
            if reason:
                skipped[reason].append(label)
                continue
            audit = approval.audit_state(source)
            channel, endpoint = approval.channel_for(source, cards, audit)
            if not endpoint or not approval.official_url(endpoint) or len(endpoint) > 1024:
                skipped['Brak RSS/API na domenie z jawnej listy'].append(label)
                continue
            latest = next((c for c in cards if c.channel == channel and c.endpoint == endpoint), None)
            result = approval.prior_result(source, channel, endpoint, audit)
            if result is not None and result[0]:
                skipped[result[0]].append(label)
                continue
            if (latest and latest.status == 'approved' and latest.valid_until
                    and latest.valid_until > timezone.now() and latest.daily_request_cap > 0
                    and latest.reviewed_at and latest.reviewed_by and latest.terms_url and latest.evidence
                    and latest.minimum_interval_seconds >= 3
                    and source.catalog_stage == 'configured' and source.is_active and source.scrape_enabled):
                skipped['Aktualna zatwierdzona karta już istnieje'].append(label)
                continue
            checked_at = timezone.now()
            if result is None:
                self.stdout.write(f'PRÓBA: {label}: {channel} {endpoint}')
                network.requests_left = 8
                result = approval.probe_channel(channel, endpoint, network)
                if apply:
                    ImportState.objects.update_or_create(name=f'public-institution-probe:{source.pk}', defaults={
                        # A completed technical audit (even a refusal) is not
                        # an importer that has never finished successfully.
                        'last_started': checked_at, 'last_success': checked_at, 'last_error': result[0][:200],
                        'cursor': {'signature': approval.source_signature(source), 'endpoint': endpoint,
                                   'channel': channel, 'reason': result[0], 'evidence': result[1]},
                    })
            reason, evidence = result
            if reason:
                skipped[reason].append(label)
                continue
            if apply:
                with transaction.atomic():
                    locked = Source.objects.select_for_update().get(pk=source.pk)
                    current = list(locked.access_instructions.order_by('-version'))
                    reason = approval.eligibility(locked, current)
                    if (reason or approval.source_signature(locked) != approval.source_signature(source)
                            or [c.pk for c in current] != [c.pk for c in cards]):
                        skipped[reason or 'Zmieniono źródło lub karty podczas kontroli; uruchom podgląd ponownie'].append(label)
                        continue
                    now = timezone.now()
                    card = SourceAccessInstruction(
                        source=locked, version=(current[0].version if current else 0) + 1,
                        status='approved', channel=channel, allowed_scope='metadata', endpoint=endpoint,
                        allowed_path_patterns=[urlsplit(endpoint).path or '/'],
                        # This URL records the owner's evidence, not a claim that
                        # the channel itself contains a publisher's licence.
                        terms_url=endpoint,
                        evidence={'channel_url': endpoint, 'basis': approval.REVIEWED_BY,
                                  'scope': approval.SCOPE_NOTE, 'technical_check': evidence},
                        minimum_interval_seconds=3, daily_request_cap=24,
                        reviewed_at=now, reviewed_by=approval.REVIEWED_BY,
                        valid_until=now + timedelta(days=90),
                    )
                    card.full_clean()
                    card.save()
                    if channel == 'rss':
                        locked.rss_url = endpoint
                    locked.catalog_stage = 'configured'
                    locked.is_active = locked.scrape_enabled = True
                    locked.full_clean()
                    locked.save()
            approved.append(label)
            self.stdout.write(f'{"ZATWIERDZONO" if apply else "PLAN"}: {label}: {channel} {endpoint}; metadane, 24/dobę, 90 dni.')
        self.stdout.write(f'Zatwierdzono: {len(approved) if apply else 0}. Do zatwierdzenia w podglądzie: {len(approved) if not apply else 0}. '
                          f'Pominięto: {sum(map(len, skipped.values()))}.')
        if approved:
            self.stdout.write('Zatwierdzone źródła:' if apply else 'Źródła do zatwierdzenia:')
            for label in approved:
                self.stdout.write(f'  - {label}')
        for reason, labels in sorted(skipped.items()):
            self.stdout.write(f'{reason}: {len(labels)}')
            for label in labels:
                self.stdout.write(f'  - {label}')
