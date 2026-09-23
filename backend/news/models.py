from __future__ import annotations

from datetime import date, timedelta

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from uuid import uuid4
from django.core.exceptions import ValidationError
from hashlib import sha256


class SourceType(models.TextChoices):
    PORTAL = "portal", "Portal"
    NEWSPAPER = "newspaper", "Prasa"
    POLITICIAN = "politician", "Polityk"
    INSTITUTION = "institution", "Instytucja"
    RSS = "rss", "RSS"
    TWITTER = "twitter", "Twitter"
    NEWSAPI = "newsapi", "NewsAPI"
    GDELT = "gdelt", "GDELT"
    EDITORIAL = "editorial", "Redakcja"


class ArticleCategory(models.TextChoices):
    VOTING = "voting", "Głosowanie Sejmu"
    LEGISLATION = "legislation", "Akt prawny / obwieszczenie"
    PARLIAMENTARY_PRINT = "parliamentary_print", "Druk sejmowy"
    REPORTAGE = "reportage", "Reportaż"
    INTERVIEW = "interview", "Wywiad"
    PODCAST = "podcast", "Podcast"
    DOCUMENT = "document", "Dokument urzędowy"
    ADVERTISEMENT = "advertisement", "Reklama"
    OTHER = "other", "Inne / nieustalona kategoria"
    STATEMENT = "statement", "Komunikat / oświadczenie"
    MENTION = "mention", "Wzmianka"
    VIDEO = "video", "Film"
    SPONSORED = "sponsored", "Sponsorowane"
    ARTICLE = "article", "Artykuł"
    TWEET = "tweet", "Tweet"
    FACTCHECK = "factcheck", "Fact-check"
    CONTEXT = "context", "Kontekst"
    OPINION = "opinion", "Opinia"


class ThreadType(models.TextChoices):
    SPONSORED = "sponsored", "Sponsorowane"
    FACTCHECK = "factcheck", "Fact-check"
    CONTEXT = "context", "Kontekst"


class Source(models.Model):
    name = models.CharField("nazwa", max_length=255)
    url = models.URLField("adres URL", unique=True, max_length=4096, blank=True, null=True)
    source_type = models.CharField(
        "typ źródła",
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.RSS,
    )
    rss_url = models.URLField("adres RSS", blank=True, max_length=4096)
    twitter_user_id = models.CharField("Twitter user ID", max_length=64, blank=True)
    is_active = models.BooleanField("aktywne", default=True)
    scrape_enabled = models.BooleanField(default=True)
    scrape_frequency_minutes = models.PositiveIntegerField(default=60)
    last_scraped = models.DateTimeField(null=True, blank=True)
    last_attempted = models.DateTimeField(null=True, blank=True)
    total_articles = models.PositiveIntegerField(default=0)
    last_tweet_id = models.CharField(max_length=64, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    catalog_notes = models.TextField("notatki katalogowe", blank=True)
    catalog_seed_key = models.CharField(max_length=64, unique=True, blank=True, null=True, editable=False)
    catalog_stage = models.CharField("etap katalogowy", max_length=16, default="configured",
        choices=[("candidate", "Kandydat"), ("configured", "Skonfigurowane"), ("excluded", "Wykluczone")],
        help_text="Skonfigurowane nie oznacza zweryfikowanego kanału ani kompletnego archiwum.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "źródło"
        verbose_name_plural = "źródła"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Preserve importer identity independently of editable name, URL and polling settings.
        if not self.catalog_seed_key and self.url:
            self.catalog_seed_key = sha256(self.url.encode('utf-8')).hexdigest()
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'catalog_seed_key'}
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        from urllib.parse import urlsplit
        errors = {}
        if not self.url:
            self.url = None
            if self.catalog_stage not in ('candidate', 'excluded') or self.is_active or self.scrape_enabled:
                errors['url'] = 'Brak adresu jest dozwolony tylko dla nieaktywnego kandydata lub źródła wykluczonego.'
        if self.catalog_stage in ('candidate', 'excluded') and (self.is_active or self.scrape_enabled):
            errors['catalog_stage'] = 'Kandydat lub źródło wykluczone musi pozostać nieaktywne. Najpierw skonfiguruj źródło.'
        if self.scrape_frequency_minutes is not None and self.scrape_frequency_minutes < 1:
            errors['scrape_frequency_minutes'] = 'Częstotliwość musi wynosić co najmniej 1 minutę.'
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values_list('url', flat=True).first()
            old_host = (urlsplit(original or '').hostname or '').lower().removeprefix('www.')
            new_host = (urlsplit(self.url or '').hostname or '').lower().removeprefix('www.')
            if old_host != new_host and (self.articles.exists() or self.archive_jobs.exists()):
                errors['url'] = 'Źródło zawiera materiały lub kolejkę archiwum. Nie można zmienić jego domeny; dodaj osobne źródło.'
        if errors:
            raise ValidationError(errors)


class SourceThumbnailPolicy(models.Model):
    """A separate, source-level decision for images and derived thumbnails."""
    class Status(models.TextChoices):
        REVIEW_REQUIRED = 'review_required', 'Wymaga kontroli pojedynczego obrazu'
        ALLOWED = 'allowed', 'Dozwolona po atrybucji'
        PROHIBITED = 'prohibited', 'Niedozwolona'

    source = models.OneToOneField(Source, on_delete=models.CASCADE, related_name='thumbnail_policy')
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REVIEW_REQUIRED)
    terms_url = models.URLField(max_length=1024)
    license_url = models.URLField(max_length=1024, blank=True)
    attribution_template = models.CharField(max_length=512, blank=True)
    evidence = models.JSONField(default=dict)
    reviewed_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.CharField(max_length=120)
    next_review_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['source__name']

    def clean(self):
        super().clean()
        if self.status == self.Status.ALLOWED and (not self.license_url or not self.attribution_template):
            raise ValidationError('Dozwolona miniatura wymaga adresu licencji i wzoru atrybucji.')


def access_instruction_default_expiry():
    return timezone.now() + timedelta(days=30)


class SourceAccessInstruction(models.Model):
    """Versioned, reviewable permission for one automated source channel.

    A configured Source is only a catalogue record.  This model is the
    fail-closed gate that permits an archive worker to use one documented
    endpoint and one explicitly reviewed scope.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Szkic'
        APPROVED = 'approved', 'Zatwierdzona'
        SUSPENDED = 'suspended', 'Wstrzymana'
        CONTACT_REQUIRED = 'contact_required', 'Wymaga kontaktu'

    class Channel(models.TextChoices):
        API = 'api', 'API'
        RSS = 'rss', 'RSS / Atom'
        EXPORT = 'export', 'Eksport danych'
        OAI_PMH = 'oai_pmh', 'OAI-PMH'
        SITEMAP = 'sitemap', 'Sitemap'
        HTML = 'html', 'Jawnie dozwolony HTML'

    class Scope(models.TextChoices):
        METADATA = 'metadata', 'Metadane'
        CONTENT = 'content', 'Treść'
        SNAPSHOT = 'snapshot', 'Snapshot'

    source = models.ForeignKey(Source, on_delete=models.CASCADE,
        related_name='access_instructions')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    allowed_scope = models.CharField(max_length=16, choices=Scope.choices, default=Scope.METADATA)
    endpoint = models.URLField(max_length=1024)
    allowed_path_patterns = models.JSONField(default=list, blank=True,
        help_text='Opcjonalne ścisłe wzorce ścieżek, np. /sejm/term10/votings/{int}.')
    terms_url = models.URLField(max_length=1024, blank=True)
    evidence = models.JSONField(default=dict, help_text='URL-e i krótkie fakty potwierdzające decyzję.')
    minimum_interval_seconds = models.PositiveIntegerField(default=3)
    daily_request_cap = models.PositiveIntegerField(default=0,
        help_text='Twardy dzienny limit żądań tej karty; 0 oznacza brak dostępu automatycznego.')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=120, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True, default=access_instruction_default_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source_id', '-version']
        constraints = [
            models.UniqueConstraint(fields=['source', 'version'], name='unique_source_access_instruction_version'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.minimum_interval_seconds < 3:
            errors['minimum_interval_seconds'] = 'Automatyczny dostęp wymaga odstępu co najmniej 3 sekund.'
        if self.status == self.Status.APPROVED and self.daily_request_cap < 1:
            errors['daily_request_cap'] = 'Zatwierdzona instrukcja wymaga dodatniego dziennego limitu żądań.'
        if not isinstance(self.allowed_path_patterns, list) or any(
                not isinstance(item, str) or not item.startswith('/') for item in self.allowed_path_patterns):
            errors['allowed_path_patterns'] = 'Wzorce ścieżek muszą być listą ścieżek rozpoczynających się od /. '
        if self.status == self.Status.APPROVED:
            if not self.terms_url:
                errors['terms_url'] = 'Zatwierdzona instrukcja wymaga linku do warunków lub licencji.'
            if not self.reviewed_at or not self.reviewed_by:
                errors['reviewed_at'] = 'Zatwierdzona instrukcja wymaga daty i autora przeglądu.'
            if not self.evidence:
                errors['evidence'] = 'Zatwierdzona instrukcja wymaga dowodu decyzji.'
            if not self.valid_until or self.valid_until <= timezone.now():
                errors['valid_until'] = 'Zatwierdzona instrukcja wymaga przyszłej daty ważności.'
        if errors:
            raise ValidationError(errors)


class FetchAttempt(models.Model):
    """Append-only receipt for a blocked or executed source fetch."""
    class Outcome(models.TextChoices):
        RESERVED = 'reserved', 'Audyt zapisany przed siecią'
        ABANDONED = 'abandoned', 'Nieukończona próba'
        REFUSED_NO_INSTRUCTION = 'refused_no_instruction', 'Brak instrukcji'
        REFUSED_EXPIRED = 'refused_expired', 'Instrukcja wygasła'
        REFUSED_SUSPENDED = 'refused_suspended', 'Instrukcja wstrzymana'
        REFUSED_SCOPE_MISMATCH = 'refused_scope_mismatch', 'Poza zakresem instrukcji'
        RATE_LIMIT_PREEMPTIVE = 'rate_limit_preemptive', 'Limit hosta przed siecią'
        DAILY_LIMIT_PREEMPTIVE = 'daily_limit_preemptive', 'Dzienny limit źródła przed siecią'
        BLOCKED_ROBOTS = 'blocked_robots', 'Zablokowane przez robots'
        OK = 'ok', 'Sukces'
        HTTP_ERROR = 'http_error', 'Błąd HTTP'
        NETWORK_ERROR = 'network_error', 'Błąd sieci'
        REDIRECTED = 'redirected', 'Przekierowanie'

    class RequestedKind(models.TextChoices):
        FEED = 'feed', 'Feed'
        SITEMAP = 'sitemap', 'Sitemap'
        PAGE = 'page', 'Strona'
        API_RECORD = 'api_record', 'Rekord API'
        ROBOTS = 'robots', 'robots.txt'
        PROBE = 'probe', 'Próba audytowa'

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='fetch_attempts')
    request_id = models.UUIDField(default=uuid4, editable=False, db_index=True)
    instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        related_name='fetch_attempts', null=True, blank=True)
    instruction_version = models.PositiveIntegerField(null=True, blank=True)
    channel = models.CharField(max_length=16, choices=SourceAccessInstruction.Channel.choices)
    requested_kind = models.CharField(max_length=16, choices=RequestedKind.choices)
    url_fingerprint = models.CharField(max_length=64, db_index=True)
    url_host = models.CharField(max_length=255, db_index=True)
    adapter_revision = models.CharField(max_length=96, blank=True)
    transport = models.CharField(max_length=48, blank=True)
    request_user_agent = models.CharField(max_length=255, blank=True)
    decision_basis = models.CharField(max_length=500, blank=True)
    attempted_at = models.DateTimeField(default=timezone.now, db_index=True)
    outcome = models.CharField(max_length=32, choices=Outcome.choices, db_index=True)
    network_started = models.BooleanField(default=False)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    bytes_received = models.PositiveBigIntegerField(default=0)
    response_sha256 = models.CharField(max_length=64, blank=True)
    redirect_target_host = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-attempted_at', '-id']
        indexes = [models.Index(fields=['source', '-attempted_at'])]

    def clean(self):
        super().clean()
        pre_network = {
            self.Outcome.RESERVED,
            self.Outcome.REFUSED_NO_INSTRUCTION,
            self.Outcome.REFUSED_EXPIRED,
            self.Outcome.REFUSED_SUSPENDED,
            self.Outcome.REFUSED_SCOPE_MISMATCH,
            self.Outcome.RATE_LIMIT_PREEMPTIVE,
            self.Outcome.DAILY_LIMIT_PREEMPTIVE,
            self.Outcome.BLOCKED_ROBOTS,
        }
        errors = {}
        if self.outcome in pre_network and self.network_started:
            errors['network_started'] = 'Odmowa przed siecią nie może oznaczać rozpoczęcia sieci.'
        if self.outcome not in pre_network and not self.network_started:
            errors['network_started'] = 'Wynik transportu wymaga rozpoczęcia sieci.'
        if self.outcome == self.Outcome.REFUSED_NO_INSTRUCTION:
            if self.instruction_id or self.instruction_version is not None:
                errors['instruction'] = 'Brak instrukcji nie może wskazywać instrukcji.'
        elif not self.instruction_id:
            errors['instruction'] = 'Każda próba poza brakiem instrukcji wymaga instrukcji źródła.'
        if self.instruction_id:
            if self.instruction_version != self.instruction.version:
                errors['instruction_version'] = 'Wersja musi odzwierciedlać wskazaną instrukcję.'
            if self.channel != self.instruction.channel:
                errors['channel'] = 'Kanał musi odpowiadać wskazanej instrukcji.'
        if self.outcome in (self.Outcome.OK, self.Outcome.HTTP_ERROR) and not self.http_status:
            errors['http_status'] = 'Wynik HTTP wymaga kodu statusu.'
        if self.outcome == self.Outcome.OK and (not self.http_status or not 200 <= self.http_status < 300):
            errors['http_status'] = 'Sukces wymaga statusu 2xx.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('FetchAttempt jest append-only i nie może być zmieniany.')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('FetchAttempt jest append-only i nie może być usuwany pojedynczo.')


class FetchRequest(models.Model):
    """Mutable control record paired with immutable FetchAttempt events."""
    class State(models.TextChoices):
        RESERVED = 'reserved', 'Zarezerwowana'
        CLOSED = 'closed', 'Zamknięta'
        ABANDONED = 'abandoned', 'Nieukończona'

    request_id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='fetch_requests')
    instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        related_name='fetch_requests')
    url_host = models.CharField(max_length=255, db_index=True)
    url_fingerprint = models.CharField(max_length=64, db_index=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.RESERVED, db_index=True)
    reserved_at = models.DateTimeField(default=timezone.now, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(state='reserved') & models.Q(closed_at__isnull=True))
                    | (~models.Q(state='reserved') & models.Q(closed_at__isnull=False))
                ),
                name='fetch_request_state_matches_closed_at',
            ),
        ]


class SourceDailyFetchBudget(models.Model):
    """Durable per-card daily reservation counter, consumed before network I/O."""
    instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        related_name='daily_fetch_budgets')
    day = models.DateField(default=date.today)
    used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['instruction', 'day'],
                name='unique_source_instruction_daily_fetch_budget'),
        ]


class HostGate(models.Model):
    """A database-backed, single-flight reservation for one remote host."""
    host = models.CharField(max_length=255, unique=True)
    locked_by = models.CharField(max_length=96)
    expires_at = models.DateTimeField(db_index=True)
    next_allowed_at = models.DateTimeField(db_index=True)


class SourceUsageDecision(models.Model):
    """Versioned decision for use of already stored material.

    This is deliberately separate from SourceAccessInstruction: the latter
    permits a future fetch, while this model governs public and AI use after a
    record already exists.  The highest version is authoritative, so a newer
    suspension never revives an older approval.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Szkic'
        APPROVED = 'approved', 'Zatwierdzona'
        SUSPENDED = 'suspended', 'Wstrzymana'

    class Use(models.TextChoices):
        PUBLIC_CARD = 'public_card', 'Karta publiczna'
        AI_DRAFT_METADATA = 'ai_draft_metadata', 'Metadane dla szkicu AI'
        RAG_INDEX = 'rag_index', 'Indeks RAG'
        OCR_EXTRACTION = 'ocr_extraction', 'OCR'
        MODEL_TRAINING = 'model_training', 'Trening modelu'

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='usage_decisions')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    allowed_uses = models.JSONField(default=list)
    applies_until_acquired_at = models.DateTimeField()
    frozen_host = models.CharField(max_length=255)
    terms_url = models.URLField(max_length=1024, blank=True)
    evidence = models.JSONField(default=dict)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=120, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source_id', '-version']
        constraints = [
            models.UniqueConstraint(fields=['source', 'version'], name='unique_source_usage_decision_version'),
        ]

    def clean(self):
        super().clean()
        valid_uses = set(self.Use.values)
        errors = {}
        if not isinstance(self.allowed_uses, list) or any(item not in valid_uses for item in self.allowed_uses):
            errors['allowed_uses'] = 'Decyzja może zawierać tylko znane sposoby użycia.'
        if self.status == self.Status.APPROVED:
            if not self.terms_url:
                errors['terms_url'] = 'Zatwierdzona decyzja wymaga linku do warunków lub licencji.'
            if not self.reviewed_at or not self.reviewed_by:
                errors['reviewed_at'] = 'Zatwierdzona decyzja wymaga daty i autora przeglądu.'
            if not self.evidence:
                errors['evidence'] = 'Zatwierdzona decyzja wymaga dowodu decyzji.'
        if errors:
            raise ValidationError(errors)


class SourceReviewDecision(models.Model):
    """A durable, non-operational decision for a catalogued source.

    It records why a candidate remains off.  It cannot enable a source or
    replace the narrow access instruction required by an importer.
    """
    class Decision(models.TextChoices):
        COVERED = 'covered', 'Pokryte aktywnym źródłem'
        TECHNICAL_RECHECK = 'technical_recheck', 'Wymaga ponownej kontroli technicznej'
        TERMS_REVIEW = 'terms_review', 'Wymaga sprawdzenia warunków'
        CHANNEL_DISCOVERY = 'channel_discovery', 'Brak potwierdzonego kanału'
        CONTACT_REQUIRED = 'contact_required', 'Wymaga późniejszego potwierdzenia'

    source = models.OneToOneField(Source, on_delete=models.CASCADE, related_name='review_decision')
    decision = models.CharField(max_length=32, choices=Decision.choices)
    reason = models.TextField()
    evidence_urls = models.JSONField(default=list, blank=True)
    audit_snapshot = models.JSONField(default=dict, blank=True)
    reviewed_by = models.CharField(max_length=120)
    reviewed_at = models.DateTimeField(default=timezone.now)
    is_automated = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['decision', 'source__name']

    def clean(self):
        super().clean()
        if self.decision == self.Decision.COVERED and self.source.is_active:
            raise ValidationError('Decyzja „pokryte” dotyczy wyłącznie kandydata z aktywnym odpowiednikiem.')
        if not isinstance(self.evidence_urls, list):
            raise ValidationError('Dowody decyzji muszą być listą adresów URL.')


class SourceRecoveryCase(models.Model):
    """A bounded diagnosis of one failed source instruction, never a bypass."""
    class Status(models.TextChoices):
        DETECTED = 'detected', 'Wykryto'
        TRIAGE = 'triage', 'Triage'
        COOLDOWN = 'cooldown', 'Przerwa techniczna'
        AUDITING = 'auditing', 'Audyt'
        DRY_RUN = 'dry_run', 'Mały test'
        REPAIRED = 'repaired', 'Naprawiono'
        MANUAL_REVIEW = 'manual_review', 'Kontrola ręczna'
        CONTACT_REQUIRED = 'contact_required', 'Wymaga kontaktu'
        RETIRED = 'retired', 'Wycofano'
        CLOSED = 'closed', 'Zamknięto'

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='recovery_cases')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DETECTED)
    trigger = models.CharField(max_length=32, choices=[
        ('no_new_boxes', 'Brak nowych boxów'), ('terminal_error', 'Błąd trwały'),
        ('retry_threshold', 'Próg ponowień'), ('quality_drift', 'Dryf jakości'), ('manual', 'Ręcznie'),
    ])
    failure_fingerprint = models.CharField(max_length=128)
    sample_error = models.CharField(max_length=500, blank=True)
    failed_instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        null=True, blank=True, related_name='failed_recovery_cases')
    proposed_instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        null=True, blank=True, related_name='proposed_recovery_cases')
    opened_at = models.DateTimeField(default=timezone.now)
    last_observed_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    boxes_before = models.PositiveIntegerField(default=0)
    boxes_after = models.PositiveIntegerField(default=0)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    audit_evidence = models.JSONField(default=dict)
    dry_run_result = models.JSONField(default=dict)
    decision_reason = models.TextField(blank=True)
    decided_by = models.CharField(max_length=120, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_observed_at', '-pk']

    def clean(self):
        super().clean()
        errors = {}
        if self.attempt_count > 2:
            errors['attempt_count'] = 'Sprawa recovery ma najwyżej dwie kontrolowane próby.'
        if self.status == self.Status.REPAIRED:
            if not self.proposed_instruction or self.proposed_instruction.status != SourceAccessInstruction.Status.APPROVED:
                errors['proposed_instruction'] = 'Naprawa wymaga zatwierdzonej instrukcji dostępu.'
            if self.boxes_after <= self.boxes_before or not self.dry_run_result.get('succeeded'):
                errors['dry_run_result'] = 'Naprawa wymaga dodatniego, udanego dry-runu.'
        if errors:
            raise ValidationError(errors)


class SourceContactCard(models.Model):
    """A reviewable draft for a future human contact; this model never sends."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Szkic'
        READY_FOR_REVIEW = 'ready_for_review', 'Gotowa do kontroli'
        APPROVED_TO_SEND = 'approved_to_send', 'Zatwierdzona do wysyłki'
        SENT = 'sent', 'Wysłano ręcznie'
        ANSWERED = 'answered', 'Odpowiedziano'
        DECLINED = 'declined', 'Odmowa'
        AGREEMENT_RECORDED = 'agreement_recorded', 'Zgoda zapisana'
        CLOSED = 'closed', 'Zamknięto'

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='contact_cards')
    recovery_case = models.OneToOneField(SourceRecoveryCase, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contact_card')
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    publisher_name = models.CharField(max_length=255, blank=True)
    contact_url = models.URLField(max_length=1024, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_evidence_url = models.URLField(max_length=1024, blank=True)
    contact_verified_at = models.DateTimeField(null=True, blank=True)
    requested_scope = models.JSONField(default=list)
    requested_channels = models.JSONField(default=list)
    technical_findings = models.JSONField(default=dict)
    reason_for_contact = models.TextField(blank=True)
    message_draft = models.TextField(blank=True)
    approval_by = models.CharField(max_length=120, blank=True)
    approval_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_reference = models.CharField(max_length=255, blank=True)
    reply_summary = models.TextField(blank=True)
    reply_evidence_url = models.URLField(max_length=1024, blank=True)
    granted_instruction = models.ForeignKey(SourceAccessInstruction, on_delete=models.PROTECT,
        null=True, blank=True, related_name='granted_contact_cards')
    next_review_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', 'next_review_at', 'pk']

    def clean(self):
        super().clean()
        errors = {}
        if self.status == self.Status.APPROVED_TO_SEND and (not self.approval_by or not self.approval_at):
            errors['approval_by'] = 'Wysyłka wymaga osoby i czasu wyraźnego zatwierdzenia.'
        if self.status == self.Status.APPROVED_TO_SEND and not self.contact_email:
            errors['contact_email'] = 'Wysyłka e-mail wymaga zweryfikowanego adresu odbiorcy.'
        if self.status == self.Status.APPROVED_TO_SEND and not self.contact_evidence_url:
            errors['contact_evidence_url'] = 'Wysyłka e-mail wymaga linku do źródła potwierdzającego adres.'
        if self.status == self.Status.APPROVED_TO_SEND and not self.contact_verified_at:
            errors['contact_verified_at'] = 'Wysyłka e-mail wymaga czasu weryfikacji adresu.'
        if self.status == self.Status.SENT and not self.sent_at:
            errors['sent_at'] = 'Status wysłano można zapisać tylko po ręcznej wysyłce.'
        if errors:
            raise ValidationError(errors)


class SourceContactReply(models.Model):
    """Inbound outreach metadata collected from the dedicated source mailbox.

    The synchroniser stores only routing facts and a short subject line.  It
    never sends mail, changes an access card, or treats an automatic reply as
    a publisher's consent.
    """
    contact_card = models.ForeignKey(SourceContactCard, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inbound_replies')
    message_id = models.CharField(max_length=998, unique=True)
    in_reply_to = models.CharField(max_length=998, blank=True)
    sender = models.CharField(max_length=512)
    subject = models.CharField(max_length=998, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    received_at_mailbox = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at_mailbox', '-pk']


class Article(models.Model):
    source = models.ForeignKey(
        Source,
        verbose_name="źródło",
        on_delete=models.CASCADE,
        related_name="articles",
    )
    title = models.CharField("tytuł", max_length=500)
    author = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True)
    tweet_id = models.CharField(max_length=64, blank=True, db_index=True)
    likes_count = models.PositiveIntegerField(default=0)
    retweets_count = models.PositiveIntegerField(default=0)
    scraped_at = models.DateTimeField(default=timezone.now, editable=False)
    url = models.URLField("adres URL", unique=True, max_length=1024)
    published_date = models.DateTimeField("data publikacji", db_index=True, null=True, blank=True)
    date_precision = models.CharField(max_length=10, default="time", choices=[("time", "Data i czas"), ("day", "Tylko dzień")])
    discovered_at = models.DateTimeField(null=True, blank=True)
    ingestion_method = models.CharField(max_length=20, default="manual", choices=[("manual", "Redakcja"), ("rss", "RSS"), ("gdelt", "GDELT"), ("newsapi", "NewsAPI"), ("x", "X"), ("sejm", "API Sejmu"), ("eli", "ELI"), ("archive", "Archiwum wydawcy"), ("youtube", "YouTube")])
    category_reviewed = models.BooleanField(default=False)
    evidence_note = models.TextField(blank=True, help_text="Jak redakcja sprawdziła pochodzenie lub treść materiału.")
    tags = models.JSONField(default=list, blank=True, help_text="Hasła jawnie podane przez wydawcę; nie są oceną treści.")
    category = models.CharField(
        "kategoria",
        max_length=32,
        choices=ArticleCategory.choices,
        default=ArticleCategory.ARTICLE,
        db_index=True,
    )
    image_url = models.URLField("obraz", max_length=1024, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "artykuł"
        verbose_name_plural = "artykuły"
        ordering = ["-published_date"]
        indexes = [
            models.Index(fields=["published_date", "category"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self) -> str:
        return self.title


class Thread(models.Model):
    title = models.CharField("tytuł", max_length=255)
    editorial_slot = models.CharField(max_length=16, blank=True, default='',
        choices=[('', 'Pozostałe nitki'), ('government', 'Przekaz dnia obozu rządzącego'),
                 ('opposition', 'Przekaz dnia opozycji')])
    slug = models.SlugField("slug", max_length=255, unique=True)
    thread_type = models.CharField(
        "typ wątku",
        max_length=32,
        choices=ThreadType.choices,
        default=ThreadType.CONTEXT,
        db_index=True,
    )
    items = models.ManyToManyField(
        Article,
        through="ThreadItem",
        related_name="threads",
        verbose_name="pozycje",
        blank=True,
    )
    is_featured = models.BooleanField("wyróżniony", default=False)
    is_sponsored = models.BooleanField("materiał sponsorowany", default=False)
    sponsor_name = models.CharField("nazwa sponsora", max_length=200, blank=True, default='')
    description = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "wątek"
        verbose_name_plural = "wątki"
        ordering = ["-updated_at"]

        constraints = [models.CheckConstraint(
            condition=(~models.Q(published=True)
                       | (~models.Q(is_sponsored=True) & ~models.Q(thread_type=ThreadType.SPONSORED))
                       | ~models.Q(sponsor_name='')),
            name='published_sponsored_thread_has_name',
        )]

    @property
    def sponsorship_active(self):
        # Keep legacy sponsored thread types labelled during the transition.
        return self.is_sponsored or self.thread_type == ThreadType.SPONSORED

    @property
    def sponsorship_label(self):
        if not self.sponsorship_active:
            return ''
        return f'Materiał sponsorowany · {self.sponsor_name}' if self.sponsor_name else 'Materiał sponsorowany'

    def clean(self):
        super().clean()
        self.sponsor_name = self.sponsor_name.strip()
        if self.published and self.sponsorship_active and not self.sponsor_name:
            from django.core.exceptions import ValidationError
            raise ValidationError({'sponsor_name': 'Przed publikacją podaj nazwę sponsora.'})

    def __str__(self) -> str:
        return self.title

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            base = slugify(self.title)[:220] or "watek"
            self.slug = base
            if Thread.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base}-{uuid4().hex[:12]}"
        super().save(*args, **kwargs)


class ThreadItem(models.Model):
    thread = models.ForeignKey(
        Thread,
        verbose_name="wątek",
        on_delete=models.CASCADE,
        related_name="thread_items",
    )
    article = models.ForeignKey(
        Article,
        verbose_name="artykuł",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="thread_items",
    )
    position = models.PositiveIntegerField("pozycja", default=0)
    editorial_note = models.TextField("notatka redakcyjna", blank=True)
    external_url = models.URLField(max_length=1024, blank=True)

    class Meta:
        verbose_name = "pozycja wątku"
        verbose_name_plural = "pozycje wątków"
        ordering = ["position", "id"]
        unique_together = ("thread", "article")

    def __str__(self) -> str:
        return f"{self.thread.slug} #{self.position}"


class OfficialRecord(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name="official_record")
    provider = models.CharField(max_length=20, choices=[("sejm", "Sejm"), ("eli", "ELI")])
    external_id = models.CharField(max_length=100)
    api_url = models.URLField(max_length=1024)
    raw_data = models.JSONField()
    fetched_at = models.DateTimeField(default=timezone.now)
    fetch_attempt = models.ForeignKey(FetchAttempt, on_delete=models.PROTECT,
        null=True, blank=True, related_name='official_records')

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "external_id"], name="unique_official_record")]


class ParliamentaryVoting(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name="voting")
    term = models.PositiveSmallIntegerField()
    sitting = models.PositiveIntegerField()
    number = models.PositiveIntegerField()
    motion = models.TextField()
    kind = models.CharField(max_length=40)
    counts = models.JSONField(default=dict)
    options = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["term", "sitting", "number"], name="unique_sejm_voting")]


class OfficialRevision(models.Model):
    record = models.ForeignKey(OfficialRecord, on_delete=models.CASCADE, related_name='revisions')
    raw_data = models.JSONField()
    fetched_at = models.DateTimeField()
    replaced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-replaced_at']


class Ballot(models.Model):
    voting = models.ForeignKey(ParliamentaryVoting, on_delete=models.CASCADE, related_name="ballots")
    mp_id = models.PositiveIntegerField()
    name = models.CharField(max_length=255, db_index=True)
    club = models.CharField(max_length=100, blank=True)
    vote = models.CharField(max_length=30)
    list_votes = models.JSONField(default=dict)

    class Meta:
        ordering = ["name", "mp_id"]
        constraints = [models.UniqueConstraint(fields=["voting", "mp_id"], name="unique_mp_ballot")]


class EvidenceLink(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="evidence_links")
    phrase = models.CharField(max_length=200, help_text="Fraza wyszukiwania powiązana ze źródłem.")
    source_url = models.URLField(max_length=1024)
    explanation = models.TextField(help_text="Dlaczego źródło uzasadnia powiązanie z tym materiałem.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["article", "phrase", "source_url"], name="unique_evidence_link")]


class ImportState(models.Model):
    name = models.CharField(max_length=100, unique=True)
    last_started = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    imported = models.PositiveIntegerField(default=0)
    cursor = models.JSONField(default=dict)


class ArchiveJob(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='archive_jobs')
    url = models.URLField(max_length=1024, unique=True)
    kind = models.CharField(max_length=10, choices=[('sitemap', 'Sitemap'), ('page', 'Strona')])
    status = models.CharField(max_length=12, default='pending', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(default=0, db_index=True)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.CharField(max_length=200, blank=True)
    discovered_at = models.DateTimeField(default=timezone.now)
    checked_at = models.DateTimeField(null=True)

class ArticleContent(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='content')
    text = models.TextField(blank=True)
    method = models.CharField(max_length=50, default='publisher_jsonld_articleBody')
    status = models.CharField(max_length=30, default='metadata_only')
    fetched_at = models.DateTimeField(default=timezone.now)
    response_sha256 = models.CharField(max_length=64)
    source_url = models.URLField(max_length=1024)


class QualityIssue(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='quality_issues')
    code = models.CharField(max_length=60)
    active = models.BooleanField(default=True, db_index=True)
    evidence = models.JSONField(default=dict)
    first_detected = models.DateTimeField(default=timezone.now)
    last_checked = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['article', 'code'], name='unique_article_quality_issue')]


class ArticleQualityProfile(models.Model):
    """Deterministic, rebuildable identity and provenance facts for an article."""
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='quality_profile')
    canonical_url = models.URLField(max_length=1024)
    canonical_sha256 = models.CharField(max_length=64, db_index=True)
    title_sha256 = models.CharField(max_length=64, db_index=True)
    content_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    provenance = models.JSONField(default=dict)
    rules_version = models.CharField(max_length=32)
    checked_at = models.DateTimeField(default=timezone.now)


class ArticleRelation(models.Model):
    """A reviewable link; articles remain independent records."""
    left = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='quality_relations_left')
    right = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='quality_relations_right')
    relation_type = models.CharField(max_length=24, choices=[('similar_publication', 'Podobna publikacja')])
    score = models.DecimalField(max_digits=5, decimal_places=4)
    evidence = models.JSONField(default=dict)
    rules_version = models.CharField(max_length=32)
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['left', 'right', 'relation_type'], name='unique_article_quality_relation'),
            models.CheckConstraint(condition=models.Q(left_id__lt=models.F('right_id')), name='article_relation_ordered'),
        ]


class SourceQualityState(models.Model):
    """Current bounded quality sample and parser-drift signal for one source."""
    source = models.OneToOneField(Source, on_delete=models.CASCADE, related_name='quality_state')
    sample_size = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict)
    baseline_metrics = models.JSONField(default=dict)
    drift = models.JSONField(default=dict)
    rules_version = models.CharField(max_length=32)
    checked_at = models.DateTimeField(default=timezone.now)


class AIResearchCall(models.Model):
    """Operational audit only: no prompts, generated text, URLs or credentials."""
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True)
    mode = models.CharField(max_length=12, choices=[('context', 'Context'), ('verify', 'Verify')])
    model = models.CharField(max_length=120)
    response_model = models.CharField(max_length=120, null=True)
    status = models.CharField(max_length=32, default='started', db_index=True)
    provider_status = models.CharField(max_length=20, null=True)
    http_status = models.PositiveSmallIntegerField(null=True)
    input_tokens = models.PositiveBigIntegerField(null=True)
    output_tokens = models.PositiveBigIntegerField(null=True)
    web_search_calls = models.PositiveIntegerField(null=True)

    class Meta:
        ordering = ['-started_at', '-pk']


from .account_models import (  # noqa: E402,F401
    SavedTopic, ArticleOpinion, ThreadOpinion, ThreadFavorite, ArticleFavorite,
    PersonalContextThread, PersonalContextThreadItem, CommentReport,
)
from .political_models import PoliticalAccount, PoliticalAccountCandidate, ParliamentaryRosterEntry, PublicFigure, PublicOffice, PublicFigureRole, PublicFigureArticleReference, RegisteredOrganisation, PublicFigureOrganisationRelation, SocialHandleEvidence, PoliticalPost, PoliticalDraft, PoliticalRead  # noqa: E402,F401
from .evidence_snapshot import (  # noqa: E402,F401
    EvidenceSnapshot,
    SnapshotArtifactType,
    SnapshotConsentStatus,
    SnapshotAllowedUse,
    SnapshotRetentionPolicy,
    EvidenceSnapshotDisabled,
    capture_snapshot,
    is_evidence_snapshot_enabled,
)
from .evidence_extraction import (  # noqa: E402,F401
    EvidenceTextExtraction,
    EvidenceExtractionStatus,
)



