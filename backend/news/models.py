from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.conf import settings
from uuid import uuid4
from django.utils import timezone
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


from .account_models import SavedTopic, ArticleOpinion  # noqa: E402,F401
from .political_models import PoliticalAccount, PoliticalPost, PoliticalDraft, PoliticalRead  # noqa: E402,F401
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
