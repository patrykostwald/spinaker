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


def register(site):
    site.register(PublicRecord, RecordsAdmin)
    site.register(PublicRecordPerson, PrivateReadOnly)
    site.register(PublicCollectionState, StatesAdmin)
    site.register(PublicCollectionJob, JobsAdmin)
