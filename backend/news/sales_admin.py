"""Panel: zapytania (raporty, piloci) i raporty tygodniowe dla instytucji (plan finansowy 6.10, ruchy 6 i 9)."""
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from news.sales_models import SalesLead, WeeklyReportIssue


@admin.register(SalesLead)
class SalesLeadAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'status', 'organisation', 'name', 'org_type', 'email', 'newsletter', 'pilot_until')
    list_filter = ('kind', 'status', 'org_type', 'newsletter')
    search_fields = ('name', 'organisation', 'email')
    readonly_fields = ('kind', 'name', 'organisation', 'org_type', 'email', 'message', 'newsletter', 'consent_version',
                       'created_at', 'confirmation_sent_at', 'confirmed_at', 'owner_notified_at', 'pilot_until')
    fields = readonly_fields[:7] + ('status', 'notes') + readonly_fields[7:]
    exclude = ('token',)
    actions = ('offer_pdf', 'grant_pilot', 'mark_contacted', 'mark_won', 'mark_lost')

    def has_add_permission(self, request):
        return False

    @admin.action(description='Oferta prywatna (PDF) - ten sam cennik dla każdego')
    def offer_pdf(self, request, queryset):
        from news.oferta_raportow import render
        lead = queryset.first()
        response = HttpResponse(render(lead.organisation or lead.name if lead else ''), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="oferta-spin-clinic-{timezone.localdate():%Y-%m-%d}.pdf"'
        return response

    @admin.action(description='Przyznaj pilota Pro (przeszłość.today, PRZESZLOSC_PILOT_DAYS dni)')
    def grant_pilot(self, request, queryset):
        from news.sales import grant_pilot
        rows = queryset.filter(kind='pilot').exclude(status='pending')
        for lead in rows:
            grant_pilot(lead)
        self.message_user(request, f'Pilot Pro przyznany: {rows.count()}. Niepotwierdzone zgłoszenia pominięto.', messages.INFO)

    @admin.action(description='Status: w rozmowie')
    def mark_contacted(self, request, queryset):
        queryset.exclude(status='pending').update(status='contacted')

    @admin.action(description='Status: umowa')
    def mark_won(self, request, queryset):
        queryset.exclude(status='pending').update(status='won')

    @admin.action(description='Status: bez umowy')
    def mark_lost(self, request, queryset):
        queryset.exclude(status='pending').update(status='lost')


@admin.register(WeeklyReportIssue)
class WeeklyReportIssueAdmin(admin.ModelAdmin):
    list_display = ('week_start', 'week_end', 'status', 'total', 'public', 'generated_at', 'files')
    list_filter = ('status',)
    readonly_fields = ('week_start', 'week_end', 'status', 'generated_at', 'public_approved_at', 'public_approved_by', 'files', 'data')
    fields = readonly_fields
    actions = ('approve_public', 'withdraw_public', 'regenerate')

    def has_add_permission(self, request):
        return False

    @admin.display(description='wypowiedzi')
    def total(self, obj):
        return (obj.data or {}).get('total', '-')

    @admin.display(description='próbka publiczna', boolean=True)
    def public(self, obj):
        return bool(obj.public_approved_at)

    @admin.display(description='pliki')
    def files(self, obj):
        if not obj.pk or not obj.pdf:
            return '-'
        return format_html('<a href="{}">PDF</a> · <a href="{}">CSV</a>',
                           reverse('admin:news_weekly_issue_file', args=[obj.pk, 'pdf']),
                           reverse('admin:news_weekly_issue_file', args=[obj.pk, 'csv']))

    def get_urls(self):
        return [path('<int:pk>/plik/<str:kind>/', self.admin_site.admin_view(self.download), name='news_weekly_issue_file'),
                *super().get_urls()]

    def download(self, request, pk, kind):
        issue = get_object_or_404(WeeklyReportIssue, pk=pk)
        blob = bytes(issue.pdf or b'') if kind == 'pdf' else bytes(issue.csv or b'')
        response = HttpResponse(blob, content_type='application/pdf' if kind == 'pdf' else 'text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="raport-tygodniowy-{issue.week_start}.{"pdf" if kind == "pdf" else "csv"}"'
        return response

    @admin.action(description='Zatwierdź próbkę publiczną (liczby zbiorcze na /dla-redakcji)')
    def approve_public(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, 'Tylko administrator zatwierdza publikację.', messages.ERROR)
            return
        n = queryset.filter(status='ready', public_approved_at__isnull=True).update(public_approved_at=timezone.now(),
                                                                                   public_approved_by=request.user)
        self.message_user(request, f'Zatwierdzone próbki: {n}.', messages.INFO)

    @admin.action(description='Zdejmij próbkę publiczną')
    def withdraw_public(self, request, queryset):
        queryset.update(public_approved_at=None, public_approved_by=None)

    @admin.action(description='Policz numer od nowa')
    def regenerate(self, request, queryset):
        from datetime import timedelta
        from news.raport_tygodniowy import generate
        for issue in queryset:
            generate(issue.week_start + timedelta(days=7), force=True)
