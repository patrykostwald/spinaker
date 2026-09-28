"""Ręczne dodanie konta X osoby z rejestru — z dowodem i potwierdzeniem członka zespołu.

  python manage.py add_political_account a_dziemianowicz --figure 459 --camp government \
      --evidence-url https://x.com/a_dziemianowicz --note "…" --confirmed-by <login> --enable

Konto przechodzi te same sprawdzenia co przy automatycznym łączeniu (identity_problem): nazwisko w nazwie konta,
bez parodii, kont chronionych i świeżych kont z małym zasięgiem. Profil osoby łączy się z kontem przez dowód
(SocialHandleEvidence), nigdy po samej nazwie. Bez --confirmed-by pokazuje tylko, co by zrobiło.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Dodaje potwierdzone konto X osoby z rejestru (z dowodem).'

    def add_arguments(self, parser):
        parser.add_argument('handle')
        parser.add_argument('--figure', type=int, required=True, help='Numer osoby w rejestrze (PublicFigure).')
        parser.add_argument('--camp', choices=['government', 'opposition'], required=True)
        parser.add_argument('--evidence-url', required=True)
        parser.add_argument('--note', default='')
        parser.add_argument('--confirmed-by', default='', help='Login członka zespołu (is_staff).')
        parser.add_argument('--enable', action='store_true', help='Od razu czytaj wpisy.')

    def handle(self, *args, handle, figure, camp, evidence_url, note, confirmed_by, enable, **options):
        from news.management.commands.link_official_x_accounts import TechnicalError, official_identity
        from news.political_candidates import CandidateResolutionError, resolve_candidate
        from news.political_models import PoliticalAccountCandidate, PublicFigure, SocialHandleEvidence
        handle = handle.lstrip('@')
        person = PublicFigure.objects.filter(pk=figure).first()
        if person is None:
            raise CommandError(f'Nie ma osoby nr {figure} w rejestrze.')
        try:
            ok, reason = official_identity(handle, person.canonical_name)
        except TechnicalError as error:
            raise CommandError(str(error))
        if not ok:
            raise CommandError(f'@{handle} nie przechodzi sprawdzenia tożsamości: {reason}')
        self.stdout.write(f'@{handle} → {person.canonical_name} · {camp}: sprawdzenie tożsamości OK')
        staff_model = get_user_model()
        staff = staff_model.objects.filter(username=confirmed_by, is_staff=True, is_active=True).first() if confirmed_by else None
        if staff is None:
            logins = ', '.join(staff_model.objects.filter(is_staff=True, is_active=True).values_list('username', flat=True)) or 'brak'
            self.stdout.write(f'Nic nie zapisano. Dodaj --confirmed-by <login> (konta zespołu: {logins}).')
            return
        note = note or f'Konto dodane ręcznie {timezone.localdate():%d.%m.%Y}; dowód: {evidence_url}.'
        candidate, _ = PoliticalAccountCandidate.objects.get_or_create(handle=handle, defaults={
            'display_name': person.canonical_name[:150], 'classification': camp, 'proposed_camp': camp,
            'confirmation_url': evidence_url, 'confirmation_note': note})
        SocialHandleEvidence.objects.get_or_create(
            platform='x', handle=handle, subject_content_type=ContentType.objects.get_for_model(PublicFigure),
            subject_object_id=person.pk, defaults={
                'evidence_url': evidence_url, 'extracted_url': f'https://x.com/{handle}', 'status': 'candidate_created',
                'candidate': candidate, 'reviewed_by': staff, 'reviewed_at': timezone.now()})
        try:
            account = resolve_candidate(candidate, staff)
        except CandidateResolutionError as error:
            raise CommandError(str(error))
        if enable and not account.enabled:
            account.enabled = True
            account.save(update_fields=['enabled'])
        self.stdout.write(self.style.SUCCESS(f'Dodane: @{account.handle} (nr {account.user_id}) → {person.canonical_name}'
                                             + (' · czytamy wpisy' if account.enabled else '')))
