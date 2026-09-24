from django.core.management.base import BaseCommand
from django.db.models import Count, OuterRef, Subquery
from django.utils import timezone
from news.models import (Article, ArchiveJob, Source, SourceAccessInstruction,
                         SourceContactCard, SourceRecoveryCase)

class Command(BaseCommand):
    help = 'Pokazuje stan aktywnych harvesterów i kolejki bez żądań sieciowych.'

    def handle(self, *args, **options):
        latest = SourceAccessInstruction.objects.filter(source=OuterRef('pk')).order_by('-version')
        active = Source.objects.filter(is_active=True, scrape_enabled=True).annotate(
            card_status=Subquery(latest.values('status')[:1]))
        sources = Source.objects.annotate(card_status=Subquery(latest.values('status')[:1]))
        jobs = dict(ArchiveJob.objects.values_list('status').annotate(n=Count('id')))
        cards = dict(sources.values_list('card_status').annotate(n=Count('id')))
        contacts = dict(SourceContactCard.objects.values_list('status').annotate(n=Count('id')))
        recoveries = dict(SourceRecoveryCase.objects.values_list('status').annotate(n=Count('id')))
        self.stdout.write(str({
            'checked_at': timezone.now().isoformat(),
            'active_sources': active.count(),
            'active_without_approved_card': active.exclude(card_status='approved').count(),
            'articles_total': Article.objects.count(),
            'source_cards': {
                status or 'missing': cards.get(status, 0)
                for status in ('approved', 'contact_required', 'draft', 'suspended', None)
            },
            'outreach': {
                'draft': contacts.get('draft', 0),
                'ready_for_review': contacts.get('ready_for_review', 0),
                'approved_to_send': contacts.get('approved_to_send', 0),
                'sent': contacts.get('sent', 0),
                'answered': contacts.get('answered', 0),
                'due_for_followup': SourceContactCard.objects.filter(
                    status='sent', next_review_at__lte=timezone.now()).count(),
            },
            'recovery_cases_open': sum(
                count for status, count in recoveries.items()
                if status not in ('closed', 'retired')
            ),
            'queue': {status: jobs.get(status, 0) for status in ('pending', 'running', 'done', 'error', 'quarantined')},
        }))
