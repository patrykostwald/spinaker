from django.contrib import admin
from news.public_records_models import PublicRecord, PublicRecordPerson, PublicCollectionState, PublicCollectionJob


class PrivateReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RecordsAdmin(PrivateReadOnly):
    list_display = ('source', 'kind', 'external_id', 'date', 'print_number', 'fetched_at')
    list_filter = ('source', 'kind', 'term')
    search_fields = ('external_id', 'title', 'print_number')
    show_full_result_count = False
    list_per_page = 50


class StatesAdmin(PrivateReadOnly):
    list_display = ('source', 'enabled', 'record_count', 'status', 'last_success_at',
                    'last_complete_at', 'last_error', 'requests_today', 'budget_day')

    @admin.display(boolean=True, description='Flaga aktywna')
    def enabled(self, obj):
        from scraper.public_records import SOURCES
        from news.repairer import flag
        return flag(SOURCES[obj.source].flag(obj.source), False)


class JobsAdmin(PrivateReadOnly):
    list_display = ('state', 'kind', 'done', 'failures', 'last_error', 'retry_at')
    list_filter = ('state__source', 'done', 'kind')
    show_full_result_count = False


class SejmVideoSpinAdmin(admin.ModelAdmin):
    """Diagnozy wystąpień z nagrań Sejmu: tylko decyzja (zatwierdź, odrzuć, wycofaj z powodem), bez edycji treści."""
    list_display = ('day', 'place', 'figure', 'status', 'verdict', 'intensity', 'rank_score', 'diagnosed_at')
    list_filter = ('status', 'place', 'day')
    raw_id_fields = ('record', 'figure')
    actions = ('approve', 'reject')
    fields = ('status', 'withdrawn_reason', 'hidden_reason', 'day', 'place', 'figure', 'record', 'video_url', 'offset_seconds',
              'offset_exact', 'headline', 'summary', 'analysis', 'techniques', 'claims', 'limitations', 'error', 'usage')

    def get_readonly_fields(self, request, obj=None):
        return [f for f in self.fields if f not in ('status', 'withdrawn_reason', 'hidden_reason')]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        if obj.status == 'withdrawn' and not obj.withdrawn_at:
            obj.withdrawn_at = timezone.now()
        if obj.hidden_reason and not obj.hidden_at:
            obj.hidden_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description='Zatwierdź')
    def approve(self, request, queryset):
        queryset.filter(status='pending_review').update(status='approved')

    @admin.action(description='Odrzuć')
    def reject(self, request, queryset):
        queryset.filter(status='pending_review').update(status='rejected')


class CitedArticleAdmin(PrivateReadOnly):
    list_display = ('url', 'first_cited_at', 'archive_status', 'check_status', 'changed_at', 'change_count')
    list_filter = ('archive_status', 'check_status')
    search_fields = ('url', 'title')


def register(site):
    from news.zrodla_models import CitedArticle, SejmVideoSpin
    site.register(SejmVideoSpin, SejmVideoSpinAdmin)
    site.register(CitedArticle, CitedArticleAdmin)
    site.register(PublicRecord, RecordsAdmin)
    site.register(PublicRecordPerson, PrivateReadOnly)
    site.register(PublicCollectionState, StatesAdmin)
    site.register(PublicCollectionJob, JobsAdmin)
