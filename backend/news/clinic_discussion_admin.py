from datetime import timedelta
from django.contrib import admin
from django.db import transaction
from django.utils import timezone
from news.account_models import AccountIdentity
from news.clinic_discussion_models import ClinicComment, ClinicCommentReport, ClinicCommentAppeal
from news.clinic_moderation import moderate


class QueueFilter(admin.SimpleListFilter):
    title = 'kolejka moderacji'
    parameter_name = 'queue'

    def lookups(self, request, model_admin):
        return [('reports', 'Nowe zgłoszenia'), ('appeals', 'Odwołania do przeglądu'), ('filter', 'Ukryte przez filtr'), ('review', 'Do przeglądu')]

    def queryset(self, request, queryset):
        if self.value() == 'reports':
            return queryset.filter(reports__isnull=False, reports__reviewed_at__isnull=True).distinct()
        if self.value() == 'appeals':
            return queryset.filter(appeal__status='pending')
        if self.value() == 'filter':
            return queryset.filter(screening='flagged', hidden_at__isnull=False, needs_review=True)
        if self.value() == 'review':
            return queryset.filter(needs_review=True)
        return queryset


class ReadOnlyContentAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ClinicComment)
class ClinicCommentAdmin(ReadOnlyContentAdmin):
    list_display = ['id', 'author', 'diagnosis', 'interview', 'daily_message', 'created_at', 'screening', 'needs_review', 'hidden_at']
    list_filter = [QueueFilter, 'screening', 'needs_review', 'hidden_at']
    list_select_related = ['author', 'diagnosis', 'interview', 'daily_message']
    search_fields = ['body', 'author__username']
    actions = ['show_comments', 'hide_comments', 'block_authors', 'unblock_authors']

    @admin.action(description='Pokaż komentarze i rozpatrz zgłoszenia', permissions=['change'])
    def show_comments(self, request, queryset):
        moderate(queryset, request.user, True)

    @admin.action(description='Ukryj komentarze i rozpatrz zgłoszenia', permissions=['change'])
    def hide_comments(self, request, queryset):
        moderate(queryset, request.user, False)

    @admin.action(description='Zablokuj autorom komentowanie na 7 dni', permissions=['change'])
    def block_authors(self, request, queryset):
        AccountIdentity.objects.filter(user_id__in=queryset.values('author_id')).update(comments_blocked_until=timezone.now() + timedelta(days=7))

    @admin.action(description='Przywróć autorom możliwość komentowania', permissions=['change'])
    def unblock_authors(self, request, queryset):
        AccountIdentity.objects.filter(user_id__in=queryset.values('author_id')).update(comments_blocked_until=None)


@admin.register(ClinicCommentReport)
class ClinicCommentReportAdmin(ReadOnlyContentAdmin):
    list_display = ['comment', 'reporter', 'reason', 'created_at', 'reviewed_at']
    list_filter = ['reviewed_at', 'reason']
    list_select_related = ['comment', 'reporter']
    actions = None


@admin.register(ClinicCommentAppeal)
class ClinicCommentAppealAdmin(ReadOnlyContentAdmin):
    list_display = ['comment', 'author', 'status', 'created_at', 'reviewed_at']
    list_filter = ['status']
    list_select_related = ['comment', 'author']
    actions = ['accept_appeals', 'reject_appeals']

    def _decide(self, request, queryset, accept):
        for appeal in queryset.filter(status='pending').select_related('comment'):
            with transaction.atomic():
                appeal.status = 'accepted' if accept else 'rejected'
                appeal.reviewed_at, appeal.reviewed_by = timezone.now(), request.user
                appeal.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
                moderate(ClinicComment.objects.filter(pk=appeal.comment_id), request.user, accept)

    @admin.action(description='Uwzględnij odwołania i przywróć komentarze', permissions=['change'])
    def accept_appeals(self, request, queryset):
        self._decide(request, queryset, True)

    @admin.action(description='Odrzuć odwołania i utrzymaj ukrycie', permissions=['change'])
    def reject_appeals(self, request, queryset):
        self._decide(request, queryset, False)
