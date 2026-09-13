"""Read-only local configuration and observed AI usage; never calls a provider."""
import json
import os
from django.core.management.base import BaseCommand
from django.db import DatabaseError
from django.db.models import Count, Sum
from django.utils import timezone
from news.ai_research import configuration, research_daily_limit
from news.external_search import allowed_sources
from news.models import AIResearchCall, ImportState


def present(name):
    return 'present' if os.environ.get(name, '').strip() else 'missing'


def attempts(name):
    state = ImportState.objects.filter(name=name).first()
    day = timezone.now().date().isoformat()
    return state.cursor.get('attempts', 0) if state and state.cursor.get('day') == day else 0


class Command(BaseCommand):
    help = 'Read-only AI preflight: configuration presence and recorded usage, without secrets or network calls.'

    def handle(self, *args, **options):
        fields = ['OPENAI_API_KEY', 'DR_SPIN_RESEARCH_MODEL', 'DR_SPIN_MODEL', 'DR_SPIN_RESEARCH_ENABLED',
                  'DR_SPIN_RESEARCH_DAILY_LIMIT', 'DR_SPIN_DAILY_CALL_LIMIT']
        sources = allowed_sources()
        research_limit = research_daily_limit()
        try:
            draft_limit = min(1000, max(0, int(os.environ.get('DR_SPIN_DAILY_CALL_LIMIT', '20'))))
        except ValueError:
            draft_limit = 0
        research_used = attempts('web-ai-daily-budget')
        draft_used = attempts('editorial-ai-daily-budget')
        ready = bool(configuration()) and 0 < len(sources) <= 100 and research_used < research_limit
        payload = {
            'checked_at': timezone.now().isoformat(),
            'configuration': {field: present(field) for field in fields},
            'allowed_domain_count': len(sources), 'allowed_domain_limit': 100,
            'research_enabled': os.environ.get('DR_SPIN_RESEARCH_ENABLED', '').lower() == 'true',
            'research_daily_attempt_limit': research_limit, 'research_attempts_today_utc': research_used,
            'editorial_daily_attempt_limit': draft_limit, 'editorial_attempts_today_utc': draft_used,
            'local_configuration_ready': {'context': ready, 'verify': ready,
                'editorial_draft': present('OPENAI_API_KEY') == 'present' and present('DR_SPIN_MODEL') == 'present' and draft_used < draft_limit},
            'verify_access': 'staff_only', 'provider_access_tested': False, 'brave_required_for_responses_web_search': False,
            'note': 'Gotowość dotyczy konfiguracji lokalnej. Nie sprawdzono dostępu modelu ani salda. Limit prób nie jest limitem ceny. Nie wykonano płatnych zapytań.',
        }
        day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            rows = AIResearchCall.objects.filter(started_at__gte=day_start)
            count = rows.count()
            observed = rows.aggregate(input_tokens=Sum('input_tokens'), output_tokens=Sum('output_tokens'), web_search_calls=Sum('web_search_calls'))
            payload['research_audit_today_utc'] = {'available': True, 'calls': count,
                'statuses': dict(rows.values('status').annotate(count=Count('id')).values_list('status', 'count')),
                'observed_totals': observed,
                'unknown_metrics': {field: rows.filter(**{field + '__isnull': True}).count() for field in observed}}
        except DatabaseError:
            payload['research_audit_today_utc'] = {'available': False, 'detail': 'Tabela audytu niedostępna; sprawdź migracje.'}
        payload['editorial_usage_audit'] = 'not_instrumented; attempt counter only'
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
