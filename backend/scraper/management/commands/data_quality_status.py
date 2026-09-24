"""Read-only operating view for the derived data-quality pipeline."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from news.models import (Article, ArticleQualityProfile, ArticleRelation,
                         ImportState, QualityIssue, SourceQualityState)


class Command(BaseCommand):
    help = 'Pokazuje stan profili jakości, flag i sygnałów dryfu bez zmiany materiałów.'

    def handle(self, *args, **options):
        article_count = Article.objects.count()
        profile_count = ArticleQualityProfile.objects.count()
        state = ImportState.objects.filter(name='quality:enrichment').first()
        active_issues = QualityIssue.objects.filter(active=True)
        by_code = dict(active_issues.values('code').annotate(total=Count('pk')).values_list('code', 'total'))
        drifted = SourceQualityState.objects.exclude(drift={}).count()
        cursor = (state.cursor if state else {}) or {}
        self.stdout.write(
            'DATA_QUALITY: '
            f'articles={article_count} profiles={profile_count} relations={ArticleRelation.objects.count()} '
            f'active_issues={active_issues.count()} drifted_sources={drifted}'
        )
        self.stdout.write(
            'DATA_QUALITY_ENRICHMENT: '
            f'last_pk={cursor.get("last_pk", 0)} checked={cursor.get("checked", 0)} '
            f'wrapped={cursor.get("wrapped", False)} last_success={state.last_success if state else "—"}'
        )
        for code in sorted(by_code):
            self.stdout.write(f'DATA_QUALITY_ISSUE {code}: {by_code[code]}')
