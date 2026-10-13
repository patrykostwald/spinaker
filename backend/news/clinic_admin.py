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


from news.clinic_models import CausalChain, CausalChainEvent  # noqa: E402


class CausalChainEventInline(admin.TabularInline):
    model = CausalChainEvent
    extra = 0
    can_delete = False
    readonly_fields = ('event', 'at', 'actor', 'model_name', 'prompt_version', 'details')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CausalChain)
class CausalChainAdmin(admin.ModelAdmin):
    """v3 „Dr Spin wyjaśnia”: kroki tylko do odczytu; człowiek zatwierdza albo odrzuca (news/causal_chain.py)."""
    list_display = ('message', 'status', 'approved_at', 'model_name', 'prompt_version', 'created_at')
    list_filter = ('status',)
    readonly_fields = tuple(f.name for f in CausalChain._meta.fields)
    inlines = [CausalChainEventInline]
    actions = ['approve_chains', 'reject_chains']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _decide(self, request, queryset, decision):
        from news import causal_chain
        done, errors = 0, []
        for chain in queryset:
            try:
                (causal_chain.approve if decision == 'approve' else causal_chain.reject)(chain, request.user)
                done += 1
            except causal_chain.ChainError as error:
                errors.append(f'{chain.pk}: {error}')
        self.message_user(request, f'Zapisano decyzje: {done}. Kroki bez zmian.', messages.SUCCESS)
        if errors:
            self.message_user(request, 'Pominięte: ' + '; '.join(errors[:10]), messages.WARNING)

    def has_decide_permission(self, request):
        return request.user.has_perm('news.can_decide_causalchain')

    @admin.action(description='Zatwierdź ciąg przyczyn (bez zmiany kroków)', permissions=['decide'])
    def approve_chains(self, request, queryset):
        self._decide(request, queryset, 'approve')

    @admin.action(description='Odrzuć ciąg przyczyn', permissions=['decide'])
    def reject_chains(self, request, queryset):
        self._decide(request, queryset, 'reject')


from news.clinic_models import PositionPair, PositionPairEvent, PositionPairReport  # noqa: E402


class PositionPairEventInline(admin.TabularInline):
    model = PositionPairEvent
    extra = 0
    can_delete = False
    readonly_fields = ('event', 'at', 'actor', 'details')

    def has_add_permission(self, request, obj=None):
        return False


class PositionPairReportInline(admin.TabularInline):
    model = PositionPairReport
    extra = 0
    can_delete = False
    readonly_fields = ('created_at', 'priority', 'verified', 'reason', 'contact', 'is_subject', 'resolved_at')
    exclude = ('ip_hash', 'user')

    def has_add_permission(self, request, obj=None):
        return False


from news.clinic_models import VerifiedReporter  # noqa: E402


@admin.register(VerifiedReporter)
class VerifiedReporterAdmin(admin.ModelAdmin):
    """Konta potwierdzone jako osoba z rejestru albo jej przedstawiciel (zgłoszenie błędu pary zdejmuje ją z API)."""
    list_display = ('user', 'figure', 'role', 'verified_at', 'revoked_at')
    raw_id_fields = ('user', 'figure', 'verified_by')
    readonly_fields = ('verified_by', 'verified_at')

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('news.can_decide_positionpair')

    has_add_permission = lambda self, request: request.user.has_perm('news.can_decide_positionpair')  # noqa: E731

    def save_model(self, request, obj, form, change):
        if not change:
            obj.verified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PositionPair)
class PositionPairAdmin(admin.ModelAdmin):
    """v3 „Wcześniej i teraz”: treść tylko do odczytu; człowiek zatwierdza albo odrzuca (news/position_pairs.py).
    Wycofanie z publicznym powodem: komenda `pary_stanowisk wycofaj`."""
    list_display = ('figure', 'topic', 'a_date', 'b_date', 'status', 'ai_suggested', 'approved_at')
    list_filter = ('status', 'ai_suggested')
    search_fields = ('figure__canonical_name', 'topic')
    readonly_fields = tuple(f.name for f in PositionPair._meta.fields)
    inlines = [PositionPairReportInline, PositionPairEventInline]
    actions = ['approve_pairs', 'reject_pairs']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _decide(self, request, queryset, decision):
        from news import position_pairs as pp
        done, errors = 0, []
        for pair in queryset:
            try:
                (pp.approve if decision == 'approve' else pp.reject)(pair, request.user)
                done += 1
            except pp.PairError as error:
                errors.append(f'{pair.pk}: {error}')
        self.message_user(request, f'Zapisano decyzje: {done}. Treść bez zmian.', messages.SUCCESS)
        if errors:
            self.message_user(request, 'Pominięte: ' + '; '.join(errors[:10]), messages.WARNING)

    def has_decide_permission(self, request):
        return request.user.has_perm('news.can_decide_positionpair')

    @admin.action(description='Zatwierdź parę (bez zmiany treści)', permissions=['decide'])
    def approve_pairs(self, request, queryset):
        self._decide(request, queryset, 'approve')

    @admin.action(description='Odrzuć parę', permissions=['decide'])
    def reject_pairs(self, request, queryset):
        self._decide(request, queryset, 'reject')


from news.clinic_models import CausalChainReport, SiteFlag, SiteFlagChange  # noqa: E402


@admin.register(CausalChainReport)
class CausalChainReportAdmin(admin.ModelAdmin):
    """Zgłoszenia błędów w ciągach przyczyn (kolejka moderacji); decyzja: komenda lancuch_przekazu odrzuc z publicznym powodem."""
    list_display = ('chain', 'priority', 'is_subject', 'created_at', 'resolved_at')
    list_filter = ('priority', 'resolved_at')
    readonly_fields = ('chain', 'reason', 'is_subject', 'priority', 'created_at', 'resolved_at')
    exclude = ('contact', 'user', 'ip_hash')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SiteFlagForm(forms.ModelForm):
    class Meta:
        model = SiteFlag
        fields = ('key', 'value', 'active_from', 'active_until', 'note')

    def clean_key(self):
        from news.v3_flags import KNOWN
        key = self.cleaned_data['key'].strip().upper()
        if key not in KNOWN:
            raise forms.ValidationError('Nieznany przełącznik. Dozwolone: ' + ', '.join(KNOWN))
        return key


@admin.register(SiteFlag)
class SiteFlagAdmin(admin.ModelAdmin):
    """Kill switch i cisza wyborcza bez restartu (docs/RUNBOOK_KILL_SWITCH.md). Każdy zapis trafia do dziennika."""
    form = SiteFlagForm
    list_display = ('key', 'value', 'active_from', 'active_until', 'changed_by', 'changed_at')
    readonly_fields = ('changed_by', 'changed_at')

    @staticmethod
    def _state(obj):
        return {'value': obj.value, 'from': obj.active_from.isoformat() if obj.active_from else None,
                'until': obj.active_until.isoformat() if obj.active_until else None, 'note': obj.note} if obj else {}

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        before = self._state(SiteFlag.objects.filter(pk=obj.pk).first()) if obj.pk else {}
        obj.changed_by, obj.changed_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)
        SiteFlagChange.objects.create(key=obj.key, before=before, after=self._state(obj), changed_by=request.user)

    def delete_model(self, request, obj):
        SiteFlagChange.objects.create(key=obj.key, before=self._state(obj), after={'deleted': True}, changed_by=request.user)
        super().delete_model(request, obj)


@admin.register(SiteFlagChange)
class SiteFlagChangeAdmin(admin.ModelAdmin):
    list_display = ('key', 'changed_by', 'changed_at')
    readonly_fields = ('key', 'before', 'after', 'changed_by', 'changed_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
