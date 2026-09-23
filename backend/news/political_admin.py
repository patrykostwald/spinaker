from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from news.political_models import PoliticalAccount, PoliticalAccountCandidate, ParliamentaryRosterEntry, PublicFigure, RegisteredOrganisation, PublicFigureOrganisationRelation, SocialHandleEvidence, PoliticalPost, PoliticalDraft, PoliticalRead
from news.political_import import create_from_preview, validate_csv
from news.political_candidates import CandidateResolutionError, resolve_candidate
from news.political_candidate_import import create_candidates_from_preview, validate_candidate_csv
from news.social_handle_discovery import ADMIN_BATCH_LIMIT, SocialDiscoveryError, discover_for_entry


class PoliticalAccountAdmin(admin.ModelAdmin):
    change_list_template = 'admin/news/politicalaccount/change_list.html'
    list_display = ['handle', 'user_id', 'camp', 'enabled', 'confirmed_at', 'last_polled_at', 'last_error']
    list_filter = ['camp', 'enabled']
    search_fields = ['handle', 'display_name', 'user_id']
    readonly_fields = ['confirmed_by', 'confirmed_at', 'confirmation_fingerprint', 'poll_cursor',
        'next_poll_at', 'last_polled_at', 'last_error', 'created_at']
    actions = ['confirm_accounts']

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='news_politicalaccount_import_csv'),
        ]
        return custom + urls

    def import_csv(self, request):
        """Two-step, staff-only import. CSV is previewed before any database write."""
        context = {**self.admin_site.each_context(request), 'title': 'Importuj konta polityczne z CSV'}
        if request.method == 'POST' and 'csv_file' in request.FILES:
            rows, errors = validate_csv(request.FILES['csv_file'])
            context.update(rows=rows, errors=errors)
            if rows and not errors and not any(row['errors'] for row in rows):
                request.session['political_account_import_preview'] = rows
                context['can_import'] = True
            return TemplateResponse(request, 'admin/news/politicalaccount/import_csv.html', context)
        if request.method == 'POST' and request.POST.get('confirm_import') == '1':
            rows = request.session.pop('political_account_import_preview', None)
            if not rows:
                self.message_user(request, 'Podgląd wygasł. Wczytaj plik ponownie.', messages.ERROR)
            else:
                try:
                    with transaction.atomic():
                        created = create_from_preview(rows)
                except ValidationError as exc:
                    self.message_user(request, '; '.join(exc.messages), messages.ERROR)
                else:
                    self.message_user(request, f'Dodano {len(created)} kont. Są wyłączone i wymagają potwierdzenia.', messages.SUCCESS)
            return HttpResponseRedirect(reverse('admin:news_politicalaccount_changelist'))
        return TemplateResponse(request, 'admin/news/politicalaccount/import_csv.html', context)

    @admin.action(description='Potwierdzam sprawdzenie tożsamości i obozu wybranych kont')
    def confirm_accounts(self, request, queryset):
        for account in queryset:
            try:
                account.confirm(request.user)
            except ValidationError as exc:
                self.message_user(request, f'@{account.handle}: {"; ".join(exc.messages)}', messages.ERROR)

    def has_delete_permission(self, request, obj=None):
        return False


class PoliticalAccountCandidateAdmin(admin.ModelAdmin):
    change_list_template = 'admin/news/politicalaccountcandidate/change_list.html'
    list_display = ['handle', 'display_name', 'classification', 'proposed_camp', 'resolved_account', 'resolved_at', 'resolution_error']
    list_filter = ['classification', 'proposed_camp']
    search_fields = ['handle', 'display_name', 'confirmation_note']
    readonly_fields = ['resolved_account', 'resolved_at', 'resolution_error', 'created_at']
    actions = ['resolve_selected_candidates']

    def get_urls(self):
        return [path('import-csv/', self.admin_site.admin_view(self.import_csv),
                     name='news_politicalaccountcandidate_import_csv')] + super().get_urls()

    def import_csv(self, request):
        context = {**self.admin_site.each_context(request), 'title': 'Importuj kandydatury kont z CSV'}
        if request.method == 'POST' and 'csv_file' in request.FILES:
            rows, errors = validate_candidate_csv(request.FILES['csv_file'])
            context.update(rows=rows, errors=errors, can_import=bool(rows and not errors and not any(row['errors'] for row in rows)))
            if context['can_import']:
                request.session['political_candidate_import_preview'] = rows
            return TemplateResponse(request, 'admin/news/politicalaccountcandidate/import_csv.html', context)
        if request.method == 'POST' and request.POST.get('confirm_import') == '1':
            rows = request.session.pop('political_candidate_import_preview', None)
            try:
                with transaction.atomic():
                    created = create_candidates_from_preview(rows or [])
            except ValidationError as exc:
                self.message_user(request, '; '.join(exc.messages), messages.ERROR)
            else:
                self.message_user(request, f'Dodano {len(created)} kandydatur. Nie wykonano zapytań do X.', messages.SUCCESS)
            return HttpResponseRedirect(reverse('admin:news_politicalaccountcandidate_changelist'))
        return TemplateResponse(request, 'admin/news/politicalaccountcandidate/import_csv.html', context)

    @admin.action(description='Zatwierdzam i sprawdzam wybrane kandydatury w X (nie włącza pobierania)')
    def resolve_selected_candidates(self, request, queryset):
        for candidate in queryset:
            try:
                account = resolve_candidate(candidate, request.user)
            except (CandidateResolutionError, ValidationError) as exc:
                PoliticalAccountCandidate.objects.filter(pk=candidate.pk).update(resolution_error=str(exc)[:240])
                self.message_user(request, f'@{candidate.handle}: {exc}', messages.ERROR)
            else:
                self.message_user(request, f'@{candidate.handle}: utworzono potwierdzone konto; pobieranie pozostaje wyłączone.', messages.SUCCESS)

    def has_delete_permission(self, request, obj=None):
        return False


class ParliamentaryRosterEntryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'source', 'club', 'district', 'active', 'last_seen_at']
    list_filter = ['source', 'active']
    search_fields = ['full_name', 'club', 'district', 'external_id']
    readonly_fields = ['source', 'external_id', 'full_name', 'club', 'district', 'profile_url', 'source_url', 'active', 'last_seen_at', 'created_at', 'updated_at']
    actions = ['discover_official_x_links']

    @admin.action(description='Wykryj jawne linki X na wybranych profilach oficjalnych (maks. 25; bez API X)')
    def discover_official_x_links(self, request, queryset):
        selected = list(queryset.filter(active=True).order_by('pk')[:ADMIN_BATCH_LIMIT])
        if not selected:
            self.message_user(request, 'Wybierz przynajmniej jeden aktywny wpis.', messages.WARNING)
            return
        found = failed = 0
        for entry in selected:
            try:
                found += len(discover_for_entry(entry))
            except SocialDiscoveryError as exc:
                failed += 1
                self.message_user(request, f'{entry.full_name}: {exc}', messages.WARNING)
        self.message_user(request, f'Sprawdzono {len(selected)} profili; wykryto {found} jawnych linków X; pominięto {failed}. Nie użyto API X.', messages.SUCCESS)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PublicFigureAdmin(admin.ModelAdmin):
    """Manual editorial register; deliberately has no social-account actions."""
    list_display = ['canonical_name', 'role_category', 'role_title', 'organisation', 'status', 'archived', 'source_checked_at']
    list_filter = ['role_category', 'status', 'archived']
    search_fields = ['canonical_name', 'role_title', 'organisation', 'political_alignment']
    autocomplete_fields = ['parliamentary_roster_entry']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['archive_selected', 'restore_selected']

    @admin.action(description='Archiwizuj wybrane wpisy (bez usuwania)')
    def archive_selected(self, request, queryset):
        queryset.update(archived=True)

    @admin.action(description='Przywróć wybrane wpisy z archiwum')
    def restore_selected(self, request, queryset):
        queryset.update(archived=False)

    def has_delete_permission(self, request, obj=None):
        return False


class RegisteredOrganisationAdmin(admin.ModelAdmin):
    list_display = ['name', 'krs_number', 'kind', 'source_checked_at', 'archived']
    list_filter = ['kind', 'archived']
    search_fields = ['name', 'krs_number']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['archive_selected', 'restore_selected']

    @admin.action(description='Archiwizuj wybrane podmioty (bez usuwania)')
    def archive_selected(self, request, queryset):
        queryset.update(archived=True)

    @admin.action(description='Przywróć wybrane podmioty z archiwum')
    def restore_selected(self, request, queryset):
        queryset.update(archived=False)

    def has_delete_permission(self, request, obj=None):
        return False


class PublicFigureOrganisationRelationAdmin(admin.ModelAdmin):
    list_display = ['public_figure', 'organisation', 'public_role', 'relation_status',
        'verification_status', 'verified_at']
    list_filter = ['verification_status', 'relation_status', 'organisation__kind']
    search_fields = ['public_figure__canonical_name', 'organisation__name', 'organisation__krs_number', 'public_role']
    autocomplete_fields = ['public_figure', 'organisation']
    readonly_fields = ['verified_by', 'verified_at', 'created_at', 'updated_at']
    actions = ['confirm_relations', 'reject_relations']

    @admin.action(description='Potwierdź wybrane relacje w źródle publicznym')
    def confirm_relations(self, request, queryset):
        for relation in queryset.filter(verification_status='pending_review'):
            try:
                relation.confirm(request.user)
            except ValidationError as exc:
                self.message_user(request, f'{relation}: {"; ".join(exc.messages)}', messages.ERROR)
            else:
                self.message_user(request, f'Potwierdzono: {relation}', messages.SUCCESS)

    @admin.action(description='Odrzuć wybrane relacje')
    def reject_relations(self, request, queryset):
        queryset.filter(verification_status='pending_review').update(verification_status='rejected')

    def has_delete_permission(self, request, obj=None):
        return False


class SocialHandleEvidenceAdmin(admin.ModelAdmin):
    list_display = ['handle', 'roster_entry', 'platform', 'status', 'observed_at', 'candidate']
    list_filter = ['platform', 'status', 'roster_entry__source']
    search_fields = ['handle', 'roster_entry__full_name', 'evidence_url']
    readonly_fields = ['roster_entry', 'platform', 'handle', 'evidence_url', 'extracted_url', 'observed_at',
        'candidate', 'reviewed_by', 'reviewed_at', 'created_at']
    actions = ['create_candidates_after_review', 'reject_evidence']

    @admin.action(description='Po przeglądzie utwórz kandydatury kont (bez API X i bez klasyfikacji obozu)')
    def create_candidates_after_review(self, request, queryset):
        count = 0
        for evidence in queryset.filter(status='pending_review'):
            display_name = (evidence.roster_entry.full_name if evidence.roster_entry_id else str(evidence.subject or 'Profil publiczny'))
            candidate, _ = PoliticalAccountCandidate.objects.get_or_create(
                handle=evidence.handle,
                defaults={
                    'display_name': display_name[:150],
                    'classification': 'independent',
                    'proposed_camp': '',
                    'confirmation_url': evidence.evidence_url,
                    'confirmation_note': (
                        f'Jawny link do konta X znaleziony na oficjalnym profilu: {evidence.extracted_url}'
                    ),
                },
            )
            evidence.candidate = candidate
            evidence.status = 'candidate_created'
            evidence.reviewed_by = request.user
            evidence.reviewed_at = timezone.now()
            evidence.save(update_fields=['candidate', 'status', 'reviewed_by', 'reviewed_at'])
            count += 1
        self.message_user(request, f'Utworzono lub połączono {count} kandydatur. Wszystkie wymagają ręcznej klasyfikacji przed sprawdzeniem w X.', messages.SUCCESS)

    @admin.action(description='Odrzuć wybrane dowody kont')
    def reject_evidence(self, request, queryset):
        queryset.filter(status='pending_review').update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())

    def has_add_permission(self, request):
        return False

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
    site.register(PoliticalAccountCandidate, PoliticalAccountCandidateAdmin)
    site.register(ParliamentaryRosterEntry, ParliamentaryRosterEntryAdmin)
    site.register(PublicFigure, PublicFigureAdmin)
    site.register(RegisteredOrganisation, RegisteredOrganisationAdmin)
    site.register(PublicFigureOrganisationRelation, PublicFigureOrganisationRelationAdmin)
    site.register(SocialHandleEvidence, SocialHandleEvidenceAdmin)
    site.register(PoliticalPost, PoliticalPostAdmin)
    site.register(PoliticalDraft, PoliticalDraftAdmin)
    site.register(PoliticalRead, ReadOnlyPoliticalAdmin)
