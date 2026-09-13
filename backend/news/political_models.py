"""Staff-confirmed political accounts; X material is separate from Article."""
from hashlib import sha256
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


CAMPS = [('government', 'Obóz rządzący'), ('opposition', 'Opozycja')]
ID_VALIDATOR = RegexValidator(r'^[1-9][0-9]{0,18}$', 'Podaj numeryczny identyfikator X.')
HANDLE_VALIDATOR = RegexValidator(r'^[A-Za-z0-9_]{1,15}$', 'Podaj nazwę konta X bez @.')


class PoliticalAccount(models.Model):
    user_id = models.CharField(max_length=19, unique=True, validators=[ID_VALIDATOR])
    handle = models.CharField(max_length=15, unique=True, validators=[HANDLE_VALIDATOR])
    display_name = models.CharField(max_length=150)
    camp = models.CharField(max_length=12, choices=CAMPS)
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
    camp_at_collection = models.CharField(max_length=12, choices=CAMPS)
    available = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-published_at', '-pk']

    def __str__(self):
        return self.post_id


class PoliticalDraft(models.Model):
    """Editorial intake only. Approval here never publishes a Thread."""
    camp = models.CharField(max_length=12, choices=CAMPS)
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
