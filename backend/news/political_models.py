"""Staff-confirmed political accounts; X material is separate from Article."""
from hashlib import sha256
import json

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


EDITORIAL_CAMPS = [('government', 'Obóz rządzący'), ('opposition', 'Opozycja')]
ACCOUNT_CAMPS = [*EDITORIAL_CAMPS, ('public', 'Instytucja publiczna')]
ACCOUNT_CANDIDATE_CLASSIFICATIONS = [
    ('government', 'Obóz rządzący'), ('opposition', 'Opozycja'),
    ('public', 'Instytucja publiczna'), ('independent', 'Niezależne / do oceny'),
]
ID_VALIDATOR = RegexValidator(r'^[1-9][0-9]{0,18}$', 'Podaj numeryczny identyfikator X.')
HANDLE_VALIDATOR = RegexValidator(r'^[A-Za-z0-9_]{1,15}$', 'Podaj nazwę konta X bez @.')


class PoliticalAccount(models.Model):
    user_id = models.CharField(max_length=19, unique=True, validators=[ID_VALIDATOR])
    handle = models.CharField(max_length=15, unique=True, validators=[HANDLE_VALIDATOR])
    display_name = models.CharField(max_length=150)
    camp = models.CharField(max_length=12, choices=ACCOUNT_CAMPS)
    confirmation_url = models.URLField(max_length=1024, blank=True,
        help_text='Publiczne źródło potwierdzające tożsamość konta i przyjętą klasyfikację.')
    confirmation_note = models.TextField(blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name='confirmed_political_accounts')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    enabled = models.BooleanField(default=False)
    poll_interval_minutes = models.PositiveSmallIntegerField(default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)])
    poll_cursor = models.JSONField(default=dict, blank=True, editable=False)
    next_poll_at = models.DateTimeField(default=timezone.now, db_index=True, editable=False)
    last_polled_at = models.DateTimeField(null=True, editable=False)
    last_error = models.CharField(max_length=120, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f'@{self.handle} — {self.get_camp_display()}'

    def identity_fingerprint(self):
        values = [self.user_id, self.handle.lower(), self.display_name, self.camp,
                  self.confirmation_url, self.confirmation_note]
        return sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()

    def clean(self):
        super().clean()
        if self.pk:
            previous = PoliticalAccount.objects.filter(pk=self.pk).first()
            if previous and previous.user_id != self.user_id and (previous.poll_cursor or previous.posts.exists()):
                raise ValidationError({'user_id': 'Konto ma historię pobrań. Dodaj osobne konto zamiast zmieniać jego identyfikator.'})

    def is_confirmed(self):
        return bool(self.confirmed_by_id and self.confirmed_at and self.confirmation_url
            and self.confirmation_fingerprint == self.identity_fingerprint()
            and self.confirmed_by.is_active and self.confirmed_by.is_staff)

    def confirm(self, staff):
        if not staff.is_active or not staff.is_staff:
            raise ValidationError('Potwierdzenie konta wymaga aktywnego redaktora.')
        self.full_clean()
        if not self.confirmation_url:
            raise ValidationError('Dodaj źródło potwierdzenia konta i obozu.')
        self.confirmed_by, self.confirmed_at = staff, timezone.now()
        self.confirmation_fingerprint = self.identity_fingerprint()
        self.save(update_fields=['confirmed_by', 'confirmed_at', 'confirmation_fingerprint'])


class PoliticalAccountCandidate(models.Model):
    """Editorial lead. It has no numeric X ID until a staff member resolves it."""
    handle = models.CharField(max_length=15, unique=True, validators=[HANDLE_VALIDATOR])
    display_name = models.CharField(max_length=150)
    classification = models.CharField(max_length=12, choices=ACCOUNT_CANDIDATE_CLASSIFICATIONS)
    proposed_camp = models.CharField(max_length=12, choices=ACCOUNT_CAMPS, blank=True,
        help_text='Wymagane przed utworzeniem konta do pobierania.')
    confirmation_url = models.URLField(max_length=1024, blank=True)
    confirmation_note = models.TextField(blank=True)
    resolution_error = models.CharField(max_length=240, blank=True, editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_account = models.OneToOneField(PoliticalAccount, null=True, blank=True,
        on_delete=models.PROTECT, related_name='candidate', editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['classification', 'handle']

    def __str__(self):
        return f'@{self.handle} — {self.get_classification_display()}'


PARLIAMENTARY_ROSTER_SOURCES = [
    ('sejm', 'Sejm RP'), ('senat', 'Senat RP'), ('ep', 'Parlament Europejski'),
]


class ParliamentaryRosterEntry(models.Model):
    """Official parliamentary roster staging. This does not create X account leads."""
    source = models.CharField(max_length=12, choices=PARLIAMENTARY_ROSTER_SOURCES)
    external_id = models.CharField(max_length=128)
    full_name = models.CharField(max_length=255)
    club = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=255, blank=True)
    profile_url = models.URLField(max_length=1024, blank=True)
    source_url = models.URLField(max_length=1024)
    term = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text='Kadencja wskazana przez oficjalny roster. Wymagana dla mandatów Sejmu.')
    active = models.BooleanField(default=True, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['source', 'full_name', 'external_id']
        constraints = [models.UniqueConstraint(fields=['source', 'external_id'], name='news_parliamentary_roster_source_id_unique')]

    def __str__(self):
        return f'{self.get_source_display()}: {self.full_name}'


PUBLIC_FIGURE_ROLE_CATEGORIES = [
    ('government', 'Rząd i administracja'),
    ('party', 'Partia lub klub parlamentarny'),
    ('parliamentary', 'Parlament krajowy'),
    ('european', 'Parlament Europejski'),
    ('local', 'Samorząd'),
    ('political', 'Inna osoba politycznie wpływowa'),
]
PUBLIC_FIGURE_STATUSES = [('current', 'Aktualna rola'), ('former', 'Była rola')]
ORGANISATION_KINDS = [
    ('foundation', 'Fundacja'),
    ('association', 'Stowarzyszenie'),
    ('company', 'Spółka'),
    ('other', 'Inny podmiot rejestrowy'),
]
ORGANISATION_RELATION_STATUSES = [('current', 'Obecna'), ('former', 'Historyczna')]
ORGANISATION_VERIFICATION_STATUSES = [
    ('pending_review', 'Wymaga potwierdzenia redakcji'),
    ('confirmed', 'Potwierdzona w źródle publicznym'),
    ('rejected', 'Odrzucona'),
]
KRS_NUMBER_VALIDATOR = RegexValidator(r'^\d{10}$', 'Numer KRS musi zawierać dokładnie 10 cyfr.')


class PublicFigure(models.Model):
    """Editorial register of people with a public political role.

    This registry is intentionally separate from parliamentary mandates and
    X intake.  Editors add each entry with public evidence; it never discovers
    or resolves social accounts on its own.
    """
    canonical_name = models.CharField(max_length=255,
        help_text='Nazwa wyświetlana; nie stanowi samodzielnego identyfikatora osoby.')
    role_category = models.CharField(max_length=16, choices=PUBLIC_FIGURE_ROLE_CATEGORIES)
    role_title = models.CharField(max_length=255)
    organisation = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=PUBLIC_FIGURE_STATUSES, default='current')
    official_profile_url = models.URLField(max_length=1024, blank=True)
    import_key = models.CharField(max_length=1024, blank=True, db_index=True,
        help_text='Techniczny klucz oficjalnego importu; nie jest kontem społecznościowym.')
    evidence_url = models.URLField(max_length=1024,
        help_text='Publiczne źródło potwierdzające rolę lub status wpisu.')
    evidence_note = models.TextField(blank=True)
    political_alignment = models.CharField(max_length=255, blank=True,
        help_text='Opcjonalna, ręczna notatka redakcyjna; nie jest ustalana automatycznie.')
    source_checked_at = models.DateTimeField(default=timezone.now)
    parliamentary_roster_entry = models.ForeignKey(ParliamentaryRosterEntry, null=True, blank=True,
        on_delete=models.PROTECT, related_name='public_figure_profiles',
        help_text='Opcjonalne, ręcznie sprawdzone połączenie z mandatem. Nie jest ustalane po nazwisku.')
    archived = models.BooleanField(default=False, db_index=True,
        help_text='Wpis archiwalny pozostaje w rejestrze i nie jest usuwany.')
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['archived', 'canonical_name']
        constraints = [
            models.UniqueConstraint(
                fields=['import_key'], condition=Q(import_key__gt=''),
                name='news_public_figure_nonempty_import_key_unique',
            ),
        ]

    def __str__(self):
        return self.canonical_name


class RegisteredOrganisation(models.Model):
    """Minimal public record for a KRS entity, without personal registry data."""
    name = models.CharField(max_length=512)
    krs_number = models.CharField(max_length=10, unique=True, validators=[KRS_NUMBER_VALIDATOR])
    kind = models.CharField(max_length=16, choices=ORGANISATION_KINDS)
    official_register_url = models.URLField(max_length=1024,
        help_text='Link do publicznego wpisu KRS albo urzędowego odpisu.')
    source_checked_at = models.DateTimeField(default=timezone.now)
    archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'name']

    def __str__(self):
        return f'{self.name} (KRS {self.krs_number})'


class PublicFigureOrganisationRelation(models.Model):
    """A reviewable, evidence-backed public relationship; never inferred by name."""
    public_figure = models.ForeignKey(PublicFigure, on_delete=models.PROTECT,
        related_name='organisation_relations')
    organisation = models.ForeignKey(RegisteredOrganisation, on_delete=models.PROTECT,
        related_name='public_figure_relations')
    public_role = models.CharField(max_length=255,
        help_text='Wyłącznie rola jawnie wskazana w źródle publicznym.')
    relation_status = models.CharField(max_length=12, choices=ORGANISATION_RELATION_STATUSES,
        default='current')
    evidence_url = models.URLField(max_length=1024,
        help_text='Bezpośredni publiczny dowód relacji; nie sam wynik dopasowania nazwiska.')
    evidence_note = models.TextField(blank=True)
    verification_status = models.CharField(max_length=20,
        choices=ORGANISATION_VERIFICATION_STATUSES, default='pending_review', db_index=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_public_figure_organisation_relations', editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['public_figure__canonical_name', 'organisation__kind', 'organisation__name']
        constraints = [models.UniqueConstraint(
            fields=['public_figure', 'organisation', 'public_role', 'relation_status'],
            name='unique_public_figure_organisation_role_status',
        )]

    def clean(self):
        super().clean()
        if self.verification_status == 'confirmed' and (not self.verified_by_id or not self.verified_at):
            raise ValidationError('Potwierdzona relacja wymaga redaktora i daty potwierdzenia.')

    def save(self, *args, **kwargs):
        """Return changed public evidence to the editorial review queue.

        A previous confirmation is evidence for the previous assertion only.
        This applies equally to edits made in Django admin and in commands.
        """
        changed_evidence_fields = ('public_figure_id', 'organisation_id', 'public_role',
            'relation_status', 'evidence_url', 'evidence_note')
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                'verification_status', *changed_evidence_fields,
            ).first()
            if previous and previous['verification_status'] == 'confirmed' and any(
                previous[field] != getattr(self, field) for field in changed_evidence_fields
            ):
                self.verification_status = 'pending_review'
                self.verified_by_id = None
                self.verified_at = None
                if kwargs.get('update_fields') is not None:
                    kwargs['update_fields'] = set(kwargs['update_fields']) | {
                        'verification_status', 'verified_by', 'verified_at', 'updated_at',
                    }
        super().save(*args, **kwargs)

    def confirm(self, staff):
        if not staff.is_active or not staff.is_staff:
            raise ValidationError('Potwierdzenie relacji wymaga aktywnego redaktora.')
        if not self.evidence_url:
            raise ValidationError('Dodaj bezpośredni publiczny dowód relacji.')
        self.verified_by = staff
        self.verified_at = timezone.now()
        self.verification_status = 'confirmed'
        self.full_clean()
        self.save(update_fields=['verified_by', 'verified_at', 'verification_status', 'updated_at'])


SOCIAL_EVIDENCE_STATUSES = [
    ('pending_review', 'Do przeglądu'),
    ('candidate_created', 'Przekazano do kandydatur'),
    ('rejected', 'Odrzucono'),
]


class SocialHandleEvidence(models.Model):
    """An explicit social link found on an official roster profile.

    This is deliberately only evidence for editorial review.  It is neither an
    X API lookup nor a polling account, and it never assigns a political camp.
    """
    # The roster relation supports the current import.  The generic subject
    # makes the same evidence table reusable later for an approved
    # PublicFigure registry without copying or reinterpreting a discovery.
    roster_entry = models.ForeignKey(ParliamentaryRosterEntry, null=True, blank=True,
        on_delete=models.PROTECT, related_name='social_handle_evidence')
    subject_content_type = models.ForeignKey(ContentType, null=True, blank=True,
        on_delete=models.PROTECT, related_name='+')
    subject_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    subject = GenericForeignKey('subject_content_type', 'subject_object_id')
    platform = models.CharField(max_length=16, choices=[('x', 'X')], default='x')
    handle = models.CharField(max_length=15, validators=[HANDLE_VALIDATOR])
    evidence_url = models.URLField(max_length=1024,
        help_text='Oficjalny profil, na którym znaleziono link.')
    extracted_url = models.URLField(max_length=1024,
        help_text='Bezpośredni link X/Twitter znaleziony na oficjalnej stronie.')
    observed_at = models.DateTimeField(default=timezone.now, editable=False)
    status = models.CharField(max_length=24, choices=SOCIAL_EVIDENCE_STATUSES,
        default='pending_review', db_index=True)
    candidate = models.ForeignKey(PoliticalAccountCandidate, null=True, blank=True,
        on_delete=models.PROTECT, related_name='social_evidence', editable=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_social_handle_evidence', editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-observed_at', 'roster_entry__full_name', 'handle']
        constraints = [models.UniqueConstraint(fields=['roster_entry', 'platform', 'handle'],
            name='news_social_evidence_roster_platform_handle_unique')]

    def __str__(self):
        label = self.roster_entry.full_name if self.roster_entry_id else 'profil'
        return f'{label}: @{self.handle}'

    def clean(self):
        super().clean()
        has_roster = bool(self.roster_entry_id)
        has_subject = bool(self.subject_content_type_id and self.subject_object_id)
        if has_roster == has_subject:
            raise ValidationError('Dowód konta musi wskazywać dokładnie jeden profil: mandat albo osobę publiczną.')
        if has_subject and self.subject_content_type.model != 'publicfigure':
            raise ValidationError('Ręczny dowód konta może dotyczyć wyłącznie rekordu osoby publicznej.')

class PoliticalPost(models.Model):
    account = models.ForeignKey(PoliticalAccount, on_delete=models.PROTECT, related_name='posts')
    post_id = models.CharField(max_length=19, unique=True, validators=[ID_VALIDATOR])
    url = models.URLField(max_length=1024)
    text = models.TextField()
    published_at = models.DateTimeField(db_index=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    source_data = models.JSONField(default=dict)
    author_data = models.JSONField(default=dict)
    media = models.JSONField(default=list)
    response_sha256 = models.CharField(max_length=64)
    camp_at_collection = models.CharField(max_length=12, choices=ACCOUNT_CAMPS)
    available = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-published_at', '-pk']

    def __str__(self):
        return self.post_id


class PoliticalDraft(models.Model):
    """Editorial intake only. Approval here never publishes a Thread."""
    camp = models.CharField(max_length=12, choices=EDITORIAL_CAMPS)
    day = models.DateField()
    title = models.CharField(max_length=250)
    posts = models.ManyToManyField(PoliticalPost, related_name='drafts')
    origin = models.CharField(max_length=20, default='editorial_selection',
        choices=[('editorial_selection', 'Wybór redakcji'), ('ai_proposal', 'Propozycja AI')])
    proposed_items = models.JSONField(default=list,
        help_text='Szkic powiązań do sprawdzenia; nie są rekordami źródłowymi.')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='pending_review', db_index=True,
        choices=[('pending_review', 'Do przeglądu'), ('approved', 'Zatwierdzony szkic'), ('rejected', 'Odrzucony')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='political_drafts_created')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='political_drafts_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title


class PoliticalRead(models.Model):
    """Conservative pre-request reservation, not a statement of X billing."""
    account = models.ForeignKey(PoliticalAccount, on_delete=models.PROTECT, related_name='api_reads')
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True)
    reserved_posts = models.PositiveSmallIntegerField()
    reserved_usd = models.DecimalField(max_digits=12, decimal_places=6)
    returned_posts = models.PositiveSmallIntegerField(null=True)
    status = models.CharField(max_length=32, default='reserved')
    http_status = models.PositiveSmallIntegerField(null=True)

    class Meta:
        ordering = ['-started_at', '-pk']
