from django import forms
from django.contrib import admin
from django.http import HttpResponse
import csv
from news.thread_moderation import RULES, decide
from news.thread_social_models import ThreadModerationReport, ThreadModerationDecision, ThreadModerationMail


class DecisionForm(forms.ModelForm):
    action = forms.ChoiceField(label='Decyzja człowieka', choices=[('', 'Wybierz'), ('hide', 'Ukryj'), ('restore', 'Przywróć')], required=False)
    rule = forms.ChoiceField(label='Punkt regulaminu', choices=[('', 'Wybierz')] + list(RULES.items()), required=False)
    explanation = forms.CharField(label='Uzasadnienie wysyłane obu stronom', widget=forms.Textarea, required=False)

    class Meta:
        model = ThreadModerationReport
        fields = []

    def clean(self):
        data = super().clean()
        if self.instance.status not in ('new', 'appeal'):
            raise forms.ValidationError('To zgłoszenie już rozpatrzono.')
        if not all(data.get(key) for key in ('action', 'rule', 'explanation')):
            raise forms.ValidationError('Wybierz decyzję, punkt regulaminu i napisz uzasadnienie.')
        return data


@admin.register(ThreadModerationReport)
class ThreadReportAdmin(admin.ModelAdmin):
    form = DecisionForm
    list_display = ('id', 'thread', 'comment', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason')
    search_fields = ('thread__title', 'details')
    readonly_fields = ('thread', 'comment', 'reporter', 'reason', 'details', 'snapshot', 'status',
                       'ai_assessment', 'appeal', 'appealed_at', 'created_at')
    fields = readonly_fields + ('action', 'rule', 'explanation')
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)
        class HumanDecisionForm(base):
            def clean(self):
                data = super().clean()
                if obj and obj.status == 'appeal' and obj.decisions.filter(moderator=request.user).exists():
                    raise forms.ValidationError('Odwołanie rozpatruje inny członek zespołu.')
                return data
        return HumanDecisionForm
    def save_model(self, request, obj, form, change):
        decide(obj.pk, request.user, form.cleaned_data['action'], form.cleaned_data['rule'], form.cleaned_data['explanation'])


@admin.action(description='Eksport rejestru do raportu przejrzystości (bez danych użytkowników)')
def export_decisions(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="moderacja-nitek.csv"'
    writer = csv.writer(response)
    writer.writerow(['id', 'data', 'decyzja', 'punkt', 'odwolanie'])
    for row in queryset:
        writer.writerow([row.pk, row.created_at.isoformat(), row.action, row.rule, row.is_appeal])
    return response


class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ThreadModerationDecision)
class DecisionAdmin(AuditAdmin):
    list_display = ('id', 'report', 'action', 'rule', 'is_appeal', 'created_at')
    list_filter = ('action', 'rule', 'is_appeal', 'created_at')
    actions = [export_decisions]


@admin.register(ThreadModerationMail)
class MailAdmin(AuditAdmin):
    list_display = ('decision', 'sent_at', 'last_attempt_at')
    list_filter = ('sent_at',)
