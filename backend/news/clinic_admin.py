"""Admin Kliniki spinu. Treść diagnoz jest tylko do odczytu — można ją wyłącznie zatwierdzić albo odrzucić."""
from django.contrib import admin, messages

from news import clinic
from news.clinic_models import ClinicDailyMessage, SpinDiagnosis, SpinOpinion, XAccountSuggestion
from news.clinic_models import InquisitorReview
from django.utils.html import format_html


@admin.register(InquisitorReview)
class InquisitorReviewAdmin(admin.ModelAdmin):
    change_form_template = 'admin/news/inquisitor_review.html'
    list_display = ('diagnosis', 'camp', 'verdict', 'decision', 'created_at')
    list_filter = ('verdict', 'camp', 'decision')
    readonly_fields = tuple(f.name for f in InquisitorReview._meta.fields) + ('diagnosis_link',)
    actions = ['approve_diagnoses', 'reject_diagnoses']

    @admin.display(description='Diagnoza (tylko odczyt)')
    def diagnosis_link(self, obj):
        return format_html('<a href="/admin/news/spindiagnosis/{}/change/">Otwórz diagnozę {}</a>', obj.diagnosis_id, obj.diagnosis_id)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def response_change(self, request, obj):
        if '_inquisitor_approve' in request.POST or '_inquisitor_reject' in request.POST:
            self._decide(request, InquisitorReview.objects.filter(pk=obj.pk),
                         'approve' if '_inquisitor_approve' in request.POST else 'reject')
        return super().response_change(request, obj)

    def _decide(self, request, queryset, decision):
        from news.inquisitor import decide
        count = sum(decide(pk, request.user, decision) for pk in queryset.values_list('pk', flat=True))
        self.message_user(request, f'Zapisano decyzje: {count}. Treść diagnoz bez zmian.')

    @admin.action(description='Zatwierdź diagnozę bez zmiany treści')
    def approve_diagnoses(self, request, queryset):
        self._decide(request, queryset, 'approve')

    @admin.action(description='Odrzuć diagnozę bez zmiany treści')
    def reject_diagnoses(self, request, queryset):
        self._decide(request, queryset, 'reject')

AI_FIELDS = ('post', 'verdict', 'intensity', 'headline', 'summary', 'analysis', 'techniques', 'claims', 'limitations',
             'triage', 'provider', 'model_name', 'prompt_version', 'usage', 'error', 'created_at', 'status',
             'reviewed_by', 'reviewed_at', 'alert_sent_at')


def _decide(decision):
    def action(modeladmin, request, queryset):
        done = 0
        for obj in queryset.filter(status='pending_review'):
            clinic.review(obj, request.user, decision)
            done += 1
        modeladmin.message_user(request, f'{"Zatwierdzono" if decision == "approve" else "Odrzucono"}: {done}.', messages.SUCCESS)
    action.short_description = 'Zatwierdź (bez zmian w treści)' if decision == 'approve' else 'Odrzuć'
    action.__name__ = f'clinic_{decision}'
    return action


@admin.register(SpinDiagnosis)
class SpinDiagnosisAdmin(admin.ModelAdmin):
    list_display = ('pk', 'status', 'verdict', 'intensity', 'headline', 'created_at')
    list_filter = ('status', 'verdict', 'post__camp_at_collection')
    search_fields = ('headline', 'post__text', 'post__account__handle')
    readonly_fields = AI_FIELDS
    fields = AI_FIELDS + ('hidden_at', 'hidden_reason')
    actions = [_decide('approve'), _decide('reject')]

    def has_add_permission(self, request):
        return False


@admin.register(ClinicDailyMessage)
class ClinicDailyMessageAdmin(admin.ModelAdmin):
    list_display = ('day', 'camp', 'status', 'created_at')
    list_filter = ('status', 'camp')
    readonly_fields = ('day', 'camp', 'message', 'themes', 'posts', 'status', 'model_name', 'prompt_version', 'usage',
                       'created_at', 'reviewed_by', 'reviewed_at', 'alert_sent_at')
    actions = [_decide('approve'), _decide('reject')]

    def has_add_permission(self, request):
        return False


@admin.register(SpinOpinion)
class SpinOpinionAdmin(admin.ModelAdmin):
    list_display = ('diagnosis', 'user', 'polarity', 'body', 'created_at')
    list_filter = ('polarity',)
    raw_id_fields = ('user', 'diagnosis')


@admin.register(XAccountSuggestion)
class XAccountSuggestionAdmin(admin.ModelAdmin):
    list_display = ('handle', 'public_figure', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('handle', 'public_figure__canonical_name')
    raw_id_fields = ('public_figure', 'submitted_by')
