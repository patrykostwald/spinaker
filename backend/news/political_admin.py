from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction

from news.political_models import PoliticalAccount, PoliticalPost, PoliticalDraft, PoliticalRead


class PoliticalAccountAdmin(admin.ModelAdmin):
    list_display = ['handle', 'user_id', 'camp', 'enabled', 'confirmed_at', 'last_polled_at', 'last_error']
    list_filter = ['camp', 'enabled']
    search_fields = ['handle', 'display_name', 'user_id']
    readonly_fields = ['confirmed_by', 'confirmed_at', 'confirmation_fingerprint', 'poll_cursor',
        'next_poll_at', 'last_polled_at', 'last_error', 'created_at']
    actions = ['confirm_accounts']

    @admin.action(description='Potwierdzam sprawdzenie tożsamości i obozu wybranych kont')
    def confirm_accounts(self, request, queryset):
        for account in queryset:
            try:
                account.confirm(request.user)
            except ValidationError as exc:
                self.message_user(request, f'@{account.handle}: {"; ".join(exc.messages)}', messages.ERROR)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyPoliticalAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + [field.name for field in self.model._meta.many_to_many]


class PoliticalPostAdmin(ReadOnlyPoliticalAdmin):
    list_display = ['post_id', 'account', 'published_at', 'fetched_at', 'available']
    list_filter = ['camp_at_collection', 'available']
    actions = ['remove_unavailable_content']

    @admin.action(description='Ukryj i usuń przechowaną treść niedostępnych postów (zgłoszenie usunięcia)')
    def remove_unavailable_content(self, request, queryset):
        with transaction.atomic():
            PoliticalDraft.objects.filter(posts__in=queryset).update(status='pending_review',
                reviewed_by=None, reviewed_at=None, proposed_items=[], notes='Źródło wycofane. Szkic wymaga ponownego przeglądu.')
            queryset.update(available=False, text='', source_data={}, author_data={}, media=[])


class PoliticalDraftAdmin(ReadOnlyPoliticalAdmin):
    list_display = ['title', 'camp', 'day', 'origin', 'status', 'reviewed_by']
    list_filter = ['camp', 'status', 'origin']
    actions = ['approve_drafts', 'reject_drafts']

    def _review(self, request, queryset, decision):
        from rest_framework.exceptions import ValidationError as APIValidationError
        from news.political_api import review_draft
        for draft in queryset:
            try:
                review_draft(draft, request.user, decision)
            except APIValidationError:
                self.message_user(request, 'Szkic ma niedostępne źródła; nie został zatwierdzony.', messages.ERROR)

    @admin.action(description='Zatwierdź szkic (bez publikacji nitki)')
    def approve_drafts(self, request, queryset):
        self._review(request, queryset, 'approved')

    @admin.action(description='Odrzuć szkic')
    def reject_drafts(self, request, queryset):
        self._review(request, queryset, 'rejected')


def register_political_admin(site):
    site.register(PoliticalAccount, PoliticalAccountAdmin)
    site.register(PoliticalPost, PoliticalPostAdmin)
    site.register(PoliticalDraft, PoliticalDraftAdmin)
    site.register(PoliticalRead, ReadOnlyPoliticalAdmin)
