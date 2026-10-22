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

from news.models import (InterviewMessage, Article, Source, Thread, ThreadItem, EvidenceLink, OfficialRecord,
    ImportState, SourceAccessInstruction, SourceRecoveryCase, SourceContactCard, SourceContactReply, FetchAttempt,
    SourceThumbnailPolicy, SourceReviewDecision)
from news.account_models import ArticleFavorite, CommentReport, PersonalContextThread
from news.thread_review_models import ThreadReview, ThreadReviewRound
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

from news.models import ArticleChangeEvent
class ArticleChangeEventAdmin(admin.ModelAdmin):
    list_display = ('detected_at', 'article', 'change_type', 'status', 'source_status', 'reviewed_at')
    list_filter = ('change_type', 'status')
    search_fields = ('article__title', 'article__url')
    readonly_fields = ('article', 'change_type', 'previous_title_sha256', 'current_title_sha256',
        'previous_content_sha256', 'current_content_sha256', 'source_status', 'evidence_snapshot',
        'details', 'detected_at', 'reviewed_at', 'reviewed_by')
    fields = readonly_fields + ('status',)

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user
        super().save_model(request, obj, form, change)

site.register(ArticleChangeEvent, ArticleChangeEventAdmin)


class SourceAccessInstructionAdmin(admin.ModelAdmin):
    list_display = ('source', 'version', 'status', 'channel', 'allowed_scope',
        'minimum_interval_seconds', 'reviewed_at', 'valid_until', 'reviewed_by')
    list_filter = ('status', 'channel', 'allowed_scope')
    search_fields = ('source__name', 'endpoint', 'terms_url', 'reviewed_by')
    autocomplete_fields = ('source',)
    readonly_fields = ('created_at',)

    def has_delete_permission(self, request, obj=None):
        # Historical access decisions stay auditable; suspend with a new decision.
        return False


class SourceThumbnailPolicyAdmin(admin.ModelAdmin):
    list_display = ('source', 'status', 'reviewed_at', 'reviewed_by', 'next_review_at')
    list_filter = ('status',)
    search_fields = ('source__name', 'terms_url', 'license_url', 'reviewed_by')
    autocomplete_fields = ('source',)
    readonly_fields = ('updated_at',)

    def has_delete_permission(self, request, obj=None):
        return False


class FetchAttemptAdmin(admin.ModelAdmin):
    list_display = ('attempted_at', 'source', 'channel', 'requested_kind', 'outcome',
        'network_started', 'http_status', 'url_host')
    list_filter = ('outcome', 'channel', 'requested_kind', 'network_started')
    search_fields = ('source__name', 'url_host', 'error_code', 'url_fingerprint')
    readonly_fields = ('source', 'instruction', 'instruction_version', 'channel', 'requested_kind',
        'url_fingerprint', 'url_host', 'attempted_at', 'outcome', 'network_started', 'http_status',
        'bytes_received', 'response_sha256', 'redirect_target_host', 'error_code')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
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
    list_display = ('source', 'publisher_name', 'contact_email', 'status', 'approval_by', 'approval_at', 'next_review_at')
    list_filter = ('status',)
    search_fields = ('source__name', 'publisher_name', 'reason_for_contact')
    autocomplete_fields = ('source', 'recovery_case', 'granted_instruction')
    readonly_fields = ('created_at', 'sent_at', 'delivery_reference')

    def has_delete_permission(self, request, obj=None):
        return False


class SourceReviewDecisionAdmin(admin.ModelAdmin):
    list_display = ('source', 'decision', 'reviewed_by', 'reviewed_at', 'is_automated')
    list_filter = ('decision', 'is_automated')
    search_fields = ('source__name', 'reason', 'reviewed_by')
    autocomplete_fields = ('source',)
    readonly_fields = ('updated_at',)

    def has_delete_permission(self, request, obj=None):
        return False


site.register(SourceAccessInstruction, SourceAccessInstructionAdmin)
site.register(SourceThumbnailPolicy, SourceThumbnailPolicyAdmin)
site.register(FetchAttempt, FetchAttemptAdmin)
site.register(SourceRecoveryCase, SourceRecoveryCaseAdmin)
site.register(SourceContactCard, SourceContactCardAdmin)
site.register(SourceContactReply)
site.register(SourceReviewDecision, SourceReviewDecisionAdmin)


class PublicationReviewInline(admin.StackedInline):
    model = ThreadReview
    fk_name = 'thread'
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('status', 'reason', 'revision', 'step', 'next_attempt_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class PersonalContextThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'signal_kind', 'item_count', 'updated_at')
    search_fields = ('title', 'owner__username', 'query')
    readonly_fields = ('owner', 'created_at', 'updated_at')
    inlines = (PublicationReviewInline,)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.owner_id is None:
            from news.thread_review import enqueue
            review = ThreadReview.objects.filter(thread=obj).first()
            enqueue(obj, review.payload.get('evidence', {}) if review else {})

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count('items'))

    @admin.display(description='materiały', ordering='_item_count')
    def item_count(self, obj):
        return obj._item_count

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ArticleFavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'article', 'created_at')
    search_fields = ('user__username', 'article__title')
    readonly_fields = ('user', 'article', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('target_label', 'reason', 'status', 'reporter', 'created_at', 'reviewed_at')
    list_filter = ('status', 'reason')
    search_fields = ('reporter__username', 'article_opinion__body', 'thread_opinion__body')
    readonly_fields = ('reporter', 'article_opinion', 'thread_opinion', 'reason', 'details', 'created_at')
    actions = ('mark_reviewed', 'mark_hidden')

    @admin.display(description='komentarz')
    def target_label(self, obj):
        return obj.article_opinion or obj.thread_opinion

    @admin.action(description='Oznacz jako rozpatrzone')
    def mark_reviewed(self, request, queryset):
        queryset.filter(status='new').update(status='reviewed', reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description='Oznacz jako ukryte')
    def mark_hidden(self, request, queryset):
        queryset.exclude(status='hidden').update(status='hidden', reviewed_by=request.user, reviewed_at=timezone.now())

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


site.register(PersonalContextThread, PersonalContextThreadAdmin)


class ReviewRoundInline(admin.StackedInline):
    model = ThreadReviewRound
    extra = 0
    can_delete = False
    fields = ('revision', 'role', 'model', 'result', 'reason', 'texts', 'created_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ThreadReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'editorial_thread', 'status', 'revision', 'step', 'updated_at')
    list_filter = ('status',)
    fields = ('thread', 'editorial_thread', 'status', 'revision', 'step', 'reason', 'next_attempt_at', 'payload', 'working_texts')
    readonly_fields = fields
    inlines = (ReviewRoundInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


site.register(ThreadReview, ThreadReviewAdmin)
site.register(ArticleFavorite, ArticleFavoriteAdmin)
site.register(CommentReport, CommentReportAdmin)


from news.political_admin import register_political_admin
register_political_admin(site)

from news import clinic_admin  # noqa: E402,F401
from news import clinic_discussion_admin  # noqa: E402,F401
from news import community_admin  # noqa: E402,F401


from news.newsletter_models import NewsletterSubscriber  # noqa: E402


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'status', 'source', 'created_at', 'confirmed_at', 'unsubscribed_at')
    list_filter = ('status', 'source')
    search_fields = ('email',)
    readonly_fields = ('token', 'consent_version', 'created_at', 'confirmation_sent_at', 'confirmed_at', 'unsubscribed_at')

from news import thread_social_admin  # noqa: E402,F401

from news.przeszlosc_models import PrzeszloscAlert  # noqa: E402


@admin.register(PrzeszloscAlert)
class PrzeszloscAlertAdmin(admin.ModelAdmin):
    """Alerty przeszłość.today: tylko podgląd i wypisanie; adres widzi wyłącznie administrator."""
    list_display = ('email', 'kind', 'query', 'figure', 'status', 'created_at', 'confirmed_at', 'last_sent_at')
    list_filter = ('status', 'kind')
    search_fields = ('email', 'query', 'figure__canonical_name')
    raw_id_fields = ('figure',)
    readonly_fields = ('token', 'key', 'consent_version', 'created_at', 'confirmation_sent_at', 'confirmed_at',
                       'unsubscribed_at', 'last_sent_at', 'sent_ids')

from news.public_records_admin import register as register_public_records
register_public_records(site)
from news import report_admin  # noqa: E402,F401
if site is not admin.site:
    report_admin.register(site)


@admin.register(InterviewMessage)
class InterviewMessageAdmin(admin.ModelAdmin):
    """Wiadomości czytelników do Dr. Spina przy głosowaniu na drugi wywiad dnia."""
    list_display = ('created_at', 'ballot', 'text')
    list_filter = ('ballot__day',)
    readonly_fields = ('ballot', 'user', 'text', 'created_at')


from news.feedback_models import BugReport, ClientNote, JourneyStep  # noqa: E402


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    """Zgłoszenia z przycisku „Zgłoś błąd” (właściciel 5.10). Zespół zmienia tylko status i notatkę."""
    list_display = ('created_at', 'kind', 'status', 'path', 'viewport', 'theme', 'text')
    list_filter = ('status', 'kind', 'theme')
    search_fields = ('text', 'path')
    readonly_fields = ('created_at', 'kind', 'text', 'path', 'viewport', 'theme', 'trail', 'contact', 'user')
    fields = ('status', 'staff_note', *readonly_fields)


@admin.register(JourneyStep)
class JourneyStepAdmin(admin.ModelAdmin):
    """Zbiorcza mapa przejść: bez osób, tylko liczniki na godzinę. Pełny raport: manage.py journey_report."""
    list_display = ('hour', 'device', 'source', 'action', 'target', 'count')
    list_filter = ('device', 'action')
    search_fields = ('source', 'target', 'action')
    readonly_fields = ('hour', 'device', 'source', 'action', 'target', 'count')

    def has_add_permission(self, request):
        return False


@admin.register(ClientNote)
class ClientNoteAdmin(admin.ModelAdmin):
    """Uwagi klientów z podglądów zbudujmi (6.10). Zespół zmienia tylko status i notatkę."""
    list_display = ('created_at', 'project', 'status', 'anchor', 'name', 'text')
    list_filter = ('status', 'project')
    search_fields = ('text', 'anchor', 'name')
    readonly_fields = ('created_at', 'project', 'page', 'x', 'y', 'anchor', 'text', 'name', 'viewport')
    fields = ('status', 'staff_note', *readonly_fields)


from news.agent_models import BuildTicket  # noqa: E402


@admin.register(BuildTicket)
class BuildTicketAdmin(admin.ModelAdmin):
    """Sprint tygodnia: tryb awaryjny, gdy panel Agenci nie działa."""
    list_display = ('id', 'title', 'status', 'effort', 'executor', 'rank', 'due_date', 'commit')
    list_filter = ('status', 'effort', 'executor')
    search_fields = ('title', 'brief')
    raw_id_fields = ('note', 'decided_by')
    actions = ('approve', 'drop')

    @admin.action(description='Buduj (zatwierdź)')
    def approve(self, request, queryset):
        from news import sprint
        for ticket in queryset.filter(status='proposed'):
            sprint.decide(ticket, 'approved', request.user)

    @admin.action(description='Nie teraz (odłóż)')
    def drop(self, request, queryset):
        from news import sprint
        for ticket in queryset.filter(status__in=('proposed', 'approved')):
            sprint.decide(ticket, 'dropped', request.user)


from news import sales_admin  # noqa: E402,F401  (zapytania i raporty tygodniowe dla instytucji)
