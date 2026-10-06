"""Admin Kliniki spinu. Treść diagnoz jest tylko do odczytu — można ją wyłącznie zatwierdzić albo odrzucić."""
from django.contrib import admin, messages
from django import forms
from django.db import transaction
from django.template.response import TemplateResponse

from news import clinic
from news.clinic_models import ClinicAuthorReply, ClinicDailyMessage, SpinDiagnosis, SpinOpinion, XAccountSuggestion
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


class WithdrawalForm(forms.Form):
    reason = forms.CharField(label='Publiczny powód wycofania', max_length=400, strip=True,
                             widget=forms.Textarea(attrs={'rows': 4, 'cols': 70}),
                             help_text='Powód będzie widoczny w rejestrze korekt. Nie wpisuj danych prywatnych.')


@admin.register(SpinDiagnosis)
class SpinDiagnosisAdmin(admin.ModelAdmin):
    list_display = ('pk', 'status', 'verdict', 'intensity', 'headline', 'created_at')
    list_filter = ('status', 'verdict', 'post__camp_at_collection')
    search_fields = ('headline', 'post__text', 'post__account__handle')
    readonly_fields = tuple(f.name for f in SpinDiagnosis._meta.fields if f.name not in ('hidden_at', 'hidden_reason'))
    fields = readonly_fields + ('hidden_at', 'hidden_reason')
    actions = [_decide('approve'), _decide('reject'), 'withdraw_diagnoses']

    @admin.action(description='Wycofaj diagnozę', permissions=['change'])
    def withdraw_diagnoses(self, request, queryset):
        form = WithdrawalForm(request.POST if 'confirm_withdrawal' in request.POST else None)
        if form.is_bound and form.is_valid():
            try:
                with transaction.atomic():
                    count = 0
                    for diagnosis in queryset.order_by('pk'):
                        clinic.withdraw(diagnosis, request.user, form.cleaned_data['reason'])
                        count += 1
            except ValueError as error:
                form.add_error(None, str(error))
            else:
                self.message_user(request, f'Wycofano diagnozy: {count}. Powód zapisano w publicznym rejestrze.', messages.SUCCESS)
                return None
        return TemplateResponse(request, 'admin/news/withdraw_diagnoses.html', {
            **self.admin_site.each_context(request), 'title': 'Wycofaj diagnozę', 'opts': self.model._meta,
            'form': form, 'diagnoses': queryset, 'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'select_across': request.POST.get('select_across', '0'),
        })

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(ClinicAuthorReply)
class ClinicAuthorReplyAdmin(admin.ModelAdmin):
    list_display = ('diagnosis', 'received_at', 'published_at', 'added_by')
    raw_id_fields = ('diagnosis',)
    readonly_fields = ('added_by',)

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.fields) if obj else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ClinicDailyMessage)
class ClinicDailyMessageAdmin(admin.ModelAdmin):
    list_display = ('day', 'camp', 'status', 'created_at')
    list_filter = ('status', 'camp')
    readonly_fields = ('day', 'camp', 'message', 'themes', 'posts', 'status', 'error', 'model_name', 'prompt_version', 'usage',
                       'created_at', 'reviewed_by', 'reviewed_at', 'alert_sent_at')
    actions = [_decide('approve'), _decide('reject')]

    def has_add_permission(self, request):
        return False


@admin.register(SpinOpinion)
class SpinOpinionAdmin(admin.ModelAdmin):
    list_display = ('diagnosis', 'user', 'polarity', 'body', 'created_at')
    list_filter = ('polarity',)
    raw_id_fields = ('user', 'diagnosis')
    readonly_fields = tuple(field.name for field in SpinOpinion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(XAccountSuggestion)
class XAccountSuggestionAdmin(admin.ModelAdmin):
    list_display = ('handle', 'public_figure', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('handle', 'public_figure__canonical_name')
    raw_id_fields = ('public_figure', 'submitted_by')
