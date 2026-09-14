from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django import forms
from rest_framework.exceptions import ValidationError as APIValidationError

from news.models import (Article, Source, Thread, ThreadItem, EvidenceLink, OfficialRecord,
    ImportState, SourceAccessInstruction, SourceRecoveryCase, SourceContactCard)
from scraper.tasks import (
    scrape_gdelt_task,
    scrape_newsapi_batch_task,
    scrape_rss_sources_task,
    scrape_twitter_politicians_task,
)


class ThreadItemInline(admin.TabularInline):
    model = ThreadItem
    extra = 1
    autocomplete_fields = ("article",)
    fields = ("article", "position", "editorial_note")
    ordering = ("position",)


class SourceCatalogForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial.update(catalog_stage='candidate', is_active=False, scrape_enabled=False)

    def clean(self):
        cleaned = super().clean()
        from news.source_catalog import public_catalog_url
        enabling = any(cleaned.get(field) and field in self.changed_data for field in ('is_active', 'scrape_enabled'))
        for field in ('url', 'rss_url'):
            if field in self.changed_data or enabling:
                try:
                    cleaned[field] = public_catalog_url(cleaned.get(field)) or (None if field == 'url' else '')
                except APIValidationError as exc:
                    self.add_error(field, forms.ValidationError([str(value) for value in exc.detail]))
        return cleaned


class SourceAdmin(admin.ModelAdmin):
    form = SourceCatalogForm
    list_display = ("name", "source_type", "catalog_stage", "is_active", "scrape_enabled", "scrape_frequency_minutes", "last_scraped", "article_count", "last_error")
    list_filter = ("source_type", "catalog_stage", "is_active", "scrape_enabled")
    search_fields = ("name", "url", "rss_url", "catalog_notes")
    readonly_fields = ('total_articles', 'last_scraped', 'last_attempted', 'last_error', 'created_at', 'updated_at')
    actions = ("scrape_now",)

    def has_delete_permission(self, request, obj=None):
        # Source's cascade would remove its archive. Disabling preserves the collected records.
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[Source]:
        return super().get_queryset(request).annotate(_article_count=Count("articles"))

    @admin.display(description="artykuły", ordering="_article_count")
    def article_count(self, obj: Source) -> int:
        return getattr(obj, "_article_count", 0)

    @admin.action(description="Pobierz teraz (scrape now)")
    def scrape_now(self, request: HttpRequest, queryset: QuerySet[Source]) -> None:
        from scraper.tasks import scrape_rss_source
        total = 0
        for source in queryset.filter(is_active=True, scrape_enabled=True).exclude(rss_url=''):
            scrape_rss_source.delay(source.pk)
            total += 1
        self.message_user(request, f'Zlecono pobranie {total} wybranych źródeł.')



class EvidenceLinkInline(admin.TabularInline):
    model = EvidenceLink
    extra = 0


class OfficialRecordInline(admin.StackedInline):
    model = OfficialRecord
    extra = 0
    fields = ('provider', 'external_id', 'api_url', 'fetched_at')
    readonly_fields = fields
    can_delete = False
    def has_add_permission(self, request, obj=None):
        return False


class ArticleAdmin(admin.ModelAdmin):
    inlines = (EvidenceLinkInline, OfficialRecordInline)
    list_display = ("title_short", "source", "category", "category_reviewed", "published_date")
    list_filter = ("category", "source", "published_date")
    search_fields = ("title", "author", "url", "source__name")
    date_hierarchy = "published_date"
    autocomplete_fields = ("source",)
    list_select_related = ("source",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="tytuł")
    def title_short(self, obj: Article) -> str:
        title = obj.title[:80] + ("…" if len(obj.title) > 80 else "")
        return format_html('<a href="{}">{}</a>', obj.url, title)


class ThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "thread_type", "created_by", "published", "is_featured", "is_sponsored", "sponsor_name", "views_count", "item_count")
    list_filter = ("thread_type", "published", "is_featured", "is_sponsored")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (ThreadItemInline,)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Thread]:
        return super().get_queryset(request).annotate(_item_count=Count("thread_items"))

    @admin.display(description="pozycje", ordering="_item_count")
    def item_count(self, obj: Thread) -> int:
        return getattr(obj, "_item_count", 0)


class SpinAdminSite(admin.AdminSite):
    site_header = "Polish News Aggregator"
    site_title = "Admin"
    index_title = "Panel redakcyjny"

    def get_urls(self):  # type: ignore[override]
        urls = super().get_urls()
        custom = [
            path("dashboard/", self.admin_view(self.dashboard_view), name="dashboard"),
        ]
        return custom + urls

    def index(
        self, request: HttpRequest, extra_context: dict[str, object] | None = None
    ) -> HttpResponse:
        extra_context = extra_context or {}
        extra_context.update(self._stats())
        return super().index(request, extra_context=extra_context)

    def dashboard_view(self, request: HttpRequest) -> TemplateResponse:
        context = {
            **self.each_context(request),
            "title": "Statystyki",
            **self._stats(),
        }
        return TemplateResponse(request, "admin/dashboard.html", context)

    def _stats(self) -> dict[str, object]:
        since = timezone.now() - timedelta(days=1)
        top_threads = (
            Thread.objects.filter(published=True).annotate(n=Count("thread_items"))
            .order_by("-views_count")[:5]
        )
        return {
            "articles_last_day": Article.objects.filter(scraped_at__gte=since).count(),
            "articles_total": Article.objects.count(),
            "sources_count": Source.objects.filter(is_active=True).count(),
            "threads_count": Thread.objects.filter(published=True).count(),
            "top_threads": top_threads,
        }


site = SpinAdminSite(name="admin")
admin.site = site  # type: ignore[misc]
admin.sites.site = site

site.register(User, UserAdmin)
site.register(Group, GroupAdmin)
site.register(Source, SourceAdmin)
site.register(Article, ArticleAdmin)
site.register(Thread, ThreadAdmin)

class ImportStateAdmin(admin.ModelAdmin):
    list_display = ('name', 'last_started', 'last_success', 'last_error', 'imported')
    readonly_fields = ('name', 'last_started', 'last_success', 'last_error', 'imported', 'cursor')
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

site.register(ImportState, ImportStateAdmin)


from news.models import QualityIssue
class QualityIssueAdmin(admin.ModelAdmin):
    list_display = ('article', 'code', 'active', 'first_detected', 'last_checked')
    list_filter = ('code', 'active')
    readonly_fields = ('article', 'code', 'active', 'evidence', 'first_detected', 'last_checked')
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
site.register(QualityIssue, QualityIssueAdmin)

from news.models import EvidenceSnapshot
class EvidenceSnapshotAdmin(admin.ModelAdmin):
    # Rows are created by news.evidence_snapshot.capture_snapshot(), never here:
    # an admin-created row would have metadata but no artifact in storage.
    list_display = ('article', 'artifact_type', 'consent_status', 'retention_policy', 'fetched_at')
    list_filter = ('artifact_type', 'consent_status', 'retention_policy')
    search_fields = ('article__title', 'source_url', 'storage_key')
    readonly_fields = ('article', 'source_url', 'fetched_at', 'content_sha256', 'artifact_type',
        'parser_version', 'storage_key', 'created_at')
    fields = readonly_fields + ('consent_status', 'retention_policy', 'retention_expires_at')

    def has_add_permission(self, request):
        return False
site.register(EvidenceSnapshot, EvidenceSnapshotAdmin)


class SourceAccessInstructionAdmin(admin.ModelAdmin):
    list_display = ('source', 'version', 'status', 'channel', 'allowed_scope',
        'minimum_interval_seconds', 'reviewed_at', 'reviewed_by')
    list_filter = ('status', 'channel', 'allowed_scope')
    search_fields = ('source__name', 'endpoint', 'terms_url', 'reviewed_by')
    autocomplete_fields = ('source',)
    readonly_fields = ('created_at',)

    def has_delete_permission(self, request, obj=None):
        # Historical access decisions stay auditable; suspend with a new decision.
        return False


class SourceRecoveryCaseAdmin(admin.ModelAdmin):
    list_display = ('source', 'status', 'trigger', 'failure_fingerprint',
        'boxes_before', 'boxes_after', 'last_observed_at')
    list_filter = ('status', 'trigger')
    search_fields = ('source__name', 'failure_fingerprint', 'sample_error')
    autocomplete_fields = ('source', 'failed_instruction', 'proposed_instruction')
    readonly_fields = ('source', 'trigger', 'failure_fingerprint', 'sample_error',
        'failed_instruction', 'opened_at', 'last_observed_at', 'boxes_before')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SourceContactCardAdmin(admin.ModelAdmin):
    list_display = ('source', 'publisher_name', 'status', 'approval_by', 'approval_at', 'next_review_at')
    list_filter = ('status',)
    search_fields = ('source__name', 'publisher_name', 'reason_for_contact')
    autocomplete_fields = ('source', 'recovery_case', 'granted_instruction')
    readonly_fields = ('created_at', 'sent_at', 'delivery_reference')

    def has_delete_permission(self, request, obj=None):
        return False


site.register(SourceAccessInstruction, SourceAccessInstructionAdmin)
site.register(SourceRecoveryCase, SourceRecoveryCaseAdmin)
site.register(SourceContactCard, SourceContactCardAdmin)


from news.political_admin import register_political_admin
register_political_admin(site)
