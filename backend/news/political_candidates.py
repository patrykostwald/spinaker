"""Explicit, staff-triggered conversion of account candidates to polling accounts."""
from __future__ import annotations

import os

import requests
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from news.political_models import PoliticalAccount, PoliticalAccountCandidate


class CandidateResolutionError(Exception):
    pass


def _bearer_token():
    token = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
    if not token:
        raise CandidateResolutionError('Brak tokenu X w konfiguracji serwera.')
    return token


def resolve_candidate(candidate, staff):
    """One deliberate X lookup. Never enables polling and never fetches a timeline."""
    if candidate.resolved_account_id:
        return candidate.resolved_account
    # A manually reviewed account may already exist (for example the initial
    # @donaldtusk setup). Linking it is safe only on an exact case-insensitive
    # handle match; keep that account's confirmation and polling settings intact.
    existing = PoliticalAccount.objects.filter(handle__iexact=candidate.handle).first()
    if existing:
        with transaction.atomic():
            candidate = PoliticalAccountCandidate.objects.select_for_update().get(pk=candidate.pk)
            if candidate.resolved_account_id:
                return candidate.resolved_account
            candidate.resolved_account = existing
            candidate.resolved_at = timezone.now()
            candidate.resolution_error = ''
            candidate.save(update_fields=['resolved_account', 'resolved_at', 'resolution_error'])
        return existing
    resolved_camp = 'public' if candidate.classification == 'public' else candidate.proposed_camp
    if not resolved_camp:
        raise CandidateResolutionError('Przed zatwierdzeniem przypisz konto do jednej z grup pobierania.')
    if not candidate.confirmation_url:
        raise CandidateResolutionError('Dodaj publiczny link potwierdzający tożsamość konta.')
    try:
        response = requests.get(
            f'https://api.x.com/2/users/by/username/{candidate.handle}',
            headers={'Authorization': f'Bearer {_bearer_token()}', 'Accept': 'application/json'},
            params={'user.fields': 'id,name,username'}, timeout=(5, 15), allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise CandidateResolutionError('Nie udało się połączyć z X.') from exc
    if response.status_code != 200:
        raise CandidateResolutionError(f'X odrzucił sprawdzenie konta (HTTP {response.status_code}).')
    try:
        data = response.json()['data']
        user_id, username = str(data['id']), str(data['username'])
    except (ValueError, KeyError, TypeError) as exc:
        raise CandidateResolutionError('X zwrócił niepełną odpowiedź dla tego konta.') from exc
    if username.lower() != candidate.handle.lower():
        raise CandidateResolutionError('Odpowiedź X nie zgadza się z wybranym handlem.')
    with transaction.atomic():
        candidate = PoliticalAccountCandidate.objects.select_for_update().get(pk=candidate.pk)
        if candidate.resolved_account_id:
            return candidate.resolved_account
        if PoliticalAccount.objects.filter(user_id=user_id).exists() or PoliticalAccount.objects.filter(handle__iexact=candidate.handle).exists():
            raise CandidateResolutionError('Takie konto jest już w kolejce politycznej.')
        account = PoliticalAccount(
            user_id=user_id, handle=candidate.handle, display_name=candidate.display_name,
            camp=resolved_camp, confirmation_url=candidate.confirmation_url,
            confirmation_note=candidate.confirmation_note, enabled=False,
        )
        account.full_clean()
        account.save()
        account.confirm(staff)
        candidate.resolved_account = account
        candidate.resolved_at = timezone.now()
        candidate.resolution_error = ''
        candidate.save(update_fields=['resolved_account', 'resolved_at', 'resolution_error'])
        return account
