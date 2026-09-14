"""Private evidentiary snapshot of a downloaded box (`Article`).

A snapshot is an internal record kept for future verification/OCR work — it
is never rendered to visitors and is unrelated to the public thumbnail
(`Article.image_url`) or to `ArticleContent` (public-facing extracted text).
See docs/EVIDENCE_SNAPSHOT.md for the storage/migration notes.

The mechanism is disabled by default: `capture_snapshot()` refuses to run
unless `settings.EVIDENCE_SNAPSHOT_ENABLED` is explicitly set. Nothing in
this repository calls it automatically — there is no scheduled task and no
bulk screenshot/image job wired to it. The database never holds the artifact
bytes or a secret; `storage_key` is only a reference into whatever backend
`news.snapshot_storage.get_snapshot_storage()` returns.
"""
from __future__ import annotations

from hashlib import sha256

from django.conf import settings
from django.db import models
from django.utils import timezone

from .snapshot_storage import SnapshotStorage, get_snapshot_storage


class SnapshotArtifactType(models.TextChoices):
    HTML = "html", "Zrzut HTML"
    IMAGE = "image", "Obraz / zrzut ekranu"
    PDF = "pdf", "PDF"
    OTHER = "other", "Inny"


class SnapshotConsentStatus(models.TextChoices):
    UNKNOWN = "unknown", "Nieustalone"
    ALLOWED = "allowed", "Dozwolone przez wydawcę lub zgodę"
    RESTRICTED = "restricted", "Ograniczone — wyłącznie wewnętrzny dowód"
    DENIED = "denied", "Odmówione — artefakt do usunięcia"


class SnapshotAllowedUse(models.TextChoices):
    TEXT_EXTRACTION = "text_extraction", "Prywatna ekstrakcja tekstu / OCR"
    RAG = "rag", "Prywatne wyszukiwanie i RAG"
    MODEL_TRAINING = "model_training", "Trening modelu"


class SnapshotRetentionPolicy(models.TextChoices):
    EVIDENCE_HOLD = "evidence_hold", "Zatrzymane jako dowód do decyzji redakcji"
    TEMPORARY = "temporary", "Tymczasowe, do automatycznego usunięcia"
    INDEFINITE = "indefinite", "Bezterminowe (wymaga okresowego przeglądu)"


class EvidenceSnapshot(models.Model):
    """Metadata about one privately stored evidentiary artifact.

    Never exposed through any public API or serializer; treat this as
    redakcja-only, like `QualityIssue` and `AIResearchCall`.
    """

    article = models.ForeignKey(
        "news.Article",
        verbose_name="box",
        on_delete=models.CASCADE,
        related_name="evidence_snapshots",
    )
    source_url = models.URLField("adres źródłowy", max_length=1024)
    fetched_at = models.DateTimeField("czas pobrania", default=timezone.now)
    content_sha256 = models.CharField("hash SHA-256 treści/obrazu", max_length=64)
    artifact_type = models.CharField(
        "typ artefaktu", max_length=16, choices=SnapshotArtifactType.choices)
    parser_version = models.CharField("wersja parsera", max_length=60)
    consent_status = models.CharField(
        "stan zgody/licencji", max_length=16,
        choices=SnapshotConsentStatus.choices, default=SnapshotConsentStatus.UNKNOWN)
    allowed_uses = models.JSONField(
        "jawnie dozwolone zastosowania", default=list, blank=True,
        help_text="Wersjonowany zakres zgody. Pusta lista nie zezwala na ekstrakcję, RAG ani trening.")
    storage_key = models.CharField(
        "prywatny klucz storage", max_length=512, db_index=True,
        help_text="Odniesienie do prywatnego backendu (news.snapshot_storage). Nigdy publiczny URL ani binaria. "
                   "Klucz jest wyznaczony z hasha treści, więc kolejne obserwacje tej samej treści mogą go współdzielić.")
    retention_policy = models.CharField(
        "polityka retencji", max_length=16,
        choices=SnapshotRetentionPolicy.choices, default=SnapshotRetentionPolicy.EVIDENCE_HOLD)
    retention_expires_at = models.DateTimeField("retencja do", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "prywatny snapshot dowodowy"
        verbose_name_plural = "prywatne snapshoty dowodowe"
        ordering = ["-fetched_at"]

    def __str__(self) -> str:
        return f"snapshot #{self.pk} box={self.article_id} ({self.artifact_type})"


class EvidenceSnapshotDisabled(Exception):
    """Raised when a snapshot capture is attempted while the feature is off."""


def is_evidence_snapshot_enabled() -> bool:
    return bool(getattr(settings, "EVIDENCE_SNAPSHOT_ENABLED", False))


def capture_snapshot(
    article,
    *,
    source_url: str,
    content: bytes,
    artifact_type: str,
    parser_version: str,
    consent_status: str = SnapshotConsentStatus.UNKNOWN,
    retention_policy: str = SnapshotRetentionPolicy.EVIDENCE_HOLD,
    retention_expires_at=None,
    allowed_uses=None,
    storage: SnapshotStorage | None = None,
) -> EvidenceSnapshot:
    """Store `content` privately and record its evidentiary metadata.

    Opt-in only: raises `EvidenceSnapshotDisabled` unless
    `settings.EVIDENCE_SNAPSHOT_ENABLED` is true. Refuses to store content
    whose consent status is already known to be denied. The artifact bytes
    are written through `storage` (default: `get_snapshot_storage()`); the
    database row records metadata only.
    """
    if not is_evidence_snapshot_enabled():
        raise EvidenceSnapshotDisabled(
            "EVIDENCE_SNAPSHOT_ENABLED is False; snapshot capture is disabled by default.")
    if consent_status in (SnapshotConsentStatus.UNKNOWN, SnapshotConsentStatus.DENIED):
        raise ValueError("Snapshot storage requires an explicit allowed or restricted consent status.")
    allowed_uses = list(allowed_uses or [])
    known_uses = set(SnapshotAllowedUse.values)
    if any(not isinstance(use, str) or use not in known_uses for use in allowed_uses):
        raise ValueError("Snapshot allowed_uses contains an unknown use.")
    if len(allowed_uses) != len(set(allowed_uses)):
        raise ValueError("Snapshot allowed_uses must not contain duplicates.")
    digest = sha256(content).hexdigest()
    key = f"{article.pk}/{artifact_type}/{digest}"
    (storage or get_snapshot_storage()).put(key, content)
    return EvidenceSnapshot.objects.create(
        article=article,
        source_url=source_url,
        fetched_at=timezone.now(),
        content_sha256=digest,
        artifact_type=artifact_type,
        parser_version=parser_version,
        consent_status=consent_status,
        allowed_uses=allowed_uses,
        storage_key=key,
        retention_policy=retention_policy,
        retention_expires_at=retention_expires_at,
    )
