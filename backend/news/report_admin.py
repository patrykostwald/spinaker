from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from news import report_data, raportysta
from news.report_models import InstitutionalReport, ReportReview, ReportObservation, REPORT_TYPES


class ReviewsInline(admin.TabularInline):
    model = ReportReview
    extra = 0
    can_delete = False
    fields = readonly_fields = ('round', 'role', 'provider', 'model', 'draft_hash', 'decision', 'response', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


class ReportsAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'audience', 'status', 'round', 'created_at', 'files')
    list_filter = ('kind', 'status', 'audience')
    readonly_fields = ('kind', 'audience', 'scope', 'status', 'gate', 'snapshot', 'draft', 'extra_roles',
                       'panel', 'round', 'phase', 'objections', 'method', 'approved_at', 'approved_by', 'files')
    fields = readonly_fields
    actions = ('approve_reports',)
    inlines = (ReviewsInline,)
    change_list_template = 'admin/news/reports_list.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [path('readiness/', self.admin_site.admin_view(self.readiness), name='news_reports_readiness'),
                path('<int:pk>/download/<str:kind>/', self.admin_site.admin_view(self.download), name='news_reports_download')] + super().get_urls()

    @admin.display(description='Pliki')
    def files(self, obj):
        if not obj.pdf:
            return '-'
        return format_html_join(' | ', '<a href="{}">{}</a>',
            ((reverse(f'{self.admin_site.name}:news_reports_download', args=[obj.pk, k]), label)
             for k, label in [('pdf', 'PDF'), ('csv', 'CSV'), ('method', 'Metoda i źródła')]))

    @admin.action(description='Zatwierdź raporty')
    def approve_reports(self, request, queryset):
        for obj in queryset:
            try:
                raportysta.approve(obj.pk, request.user)
                self.message_user(request, f'Raport {obj.pk} zatwierdzony.')
            except (ValueError, PermissionError) as error:
                self.message_user(request, str(error), level=messages.ERROR)

    def download(self, request, pk, kind):
        if not self.has_view_permission(request):
            return HttpResponseForbidden()
        report = get_object_or_404(InstitutionalReport, pk=pk)
        if (kind not in ('pdf', 'csv', 'method') or report.status not in ('awaiting_approval', 'approved')
                or not report.pdf or raportysta.artifact_fingerprint(report) != report.artifact_hash
                or not report_data.sources_current(report.snapshot)):
            return HttpResponseBadRequest('Plik nie jest dostępny. Sprawdź stan raportu.')
        content_type, extension = {'pdf': ('application/pdf', 'pdf'), 'csv': ('text/csv; charset=utf-8', 'csv'),
                                   'method': ('text/plain; charset=utf-8', 'txt')}[kind]
        response = HttpResponse(getattr(report, kind), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="report-{pk}.{extension}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def readiness(self, request):
        if not self.has_view_permission(request):
            return HttpResponseForbidden()
        try:
            figure_id = int(request.GET['figure_id']) if request.GET.get('figure_id') else None
        except ValueError:
            return HttpResponseBadRequest('Nieprawidłowy identyfikator osoby.')
        scope = {'figure_id': figure_id} if figure_id else {}
        topic = request.GET.get('topic', '').strip()
        if topic:
            scope['topic'] = topic
        if request.method == 'POST':
            if not request.user.is_superuser:
                return HttpResponseForbidden()
            try:
                requested_scope = {}
                if request.POST.get('figure_id'):
                    requested_scope['figure_id'] = int(request.POST['figure_id'])
                if request.POST.get('topic'):
                    requested_scope['topic'] = request.POST['topic'].strip()
                report = raportysta.request_sample(request.POST.get('kind'), request.POST.get('audience'), requested_scope)
                self.message_user(request, f'Raport {report.pk}: {report.get_status_display()}.')
            except ValueError as error:
                self.message_user(request, str(error), level=messages.ERROR)
        return TemplateResponse(request, 'admin/news/reports_readiness.html', {
            **self.admin_site.each_context(request), 'title': 'Gotowość raportów',
            'readiness': report_data.readiness(scope), 'types': REPORT_TYPES,
            'audiences': settings.REPORTS_AUDIENCES, 'enabled': settings.REPORTS_ENABLED,
            'daily_calls': settings.REPORTS_DAILY_CALLS, 'figure_id': figure_id or '', 'topic': topic,
            'opts': self.model._meta})


class ObservationsAdmin(admin.ModelAdmin):
    list_display = ('external_key', 'kind', 'topic', 'day', 'confidence', 'approved')
    list_filter = ('kind', 'topic', 'approved', 'confidence')
    readonly_fields = ('approved', 'verified_by', 'verified_at')
    raw_id_fields = ('figure', 'diagnosis', 'ballot')
    actions = ('verify', 'withdraw')

    @admin.action(description='Potwierdź źródła i własny opis analityczny')
    def verify(self, request, queryset):
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        if not request.user.is_superuser:
            self.message_user(request, 'Weryfikacja wymaga uprawnień administratora.', level=messages.ERROR)
            return
        for row in queryset:
            try:
                row.full_clean()
                row.approved, row.verified_by, row.verified_at = True, request.user, timezone.now()
                row.save()
            except ValidationError as error:
                self.message_user(request, '; '.join(error.messages), level=messages.ERROR)

    @admin.action(description='Wycofaj obserwacje')
    def withdraw(self, request, queryset):
        if request.user.is_superuser:
            queryset.update(approved=False, verified_by=None, verified_at=None)

    def has_delete_permission(self, request, obj=None):
        return False


def register(site):
    site.register(InstitutionalReport, ReportsAdmin)
    site.register(ReportObservation, ObservationsAdmin)


register(admin.site)
