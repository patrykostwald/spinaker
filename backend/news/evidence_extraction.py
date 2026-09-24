"""Private, opt-in text extraction for explicitly allowed evidence snapshots.

This module has no API, task, signal or scheduler integration. Callers must opt
in through settings and invoke ``extract_snapshot_text`` explicitly.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import re

from django.conf import settings
from django.db import models
from django.utils import timezone

from .evidence_snapshot import (
    EvidenceSnapshot, SnapshotAllowedUse, SnapshotArtifactType, SnapshotConsentStatus)
from .snapshot_storage import SnapshotStorage, get_snapshot_storage


PIPELINE_VERSION = "evidence-text-v1"


class EvidenceExtractionStatus(models.TextChoices):
    PENDING = "pending", "Oczekuje"
    SUCCEEDED = "succeeded", "Gotowe"
    FAILED = "failed", "Błąd"


class EvidenceTextExtraction(models.Model):
    """Versioned private text derived from one snapshot and its box."""

    snapshot = models.ForeignKey(
        EvidenceSnapshot, on_delete=models.CASCADE, related_name="text_extractions")
    article = models.ForeignKey(
        "news.Article", on_delete=models.CASCADE, related_name="evidence_text_extractions")
    method = models.CharField(max_length=32)
    pipeline_version = models.CharField(max_length=60)
    engine_version = models.CharField(max_length=120, blank=True)
    input_sha256 = models.CharField(max_length=64)
    text_sha256 = models.CharField(max_length=64, blank=True)
    text = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=EvidenceExtractionStatus.choices,
        default=EvidenceExtractionStatus.PENDING)
    language = models.CharField(max_length=32, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(
            fields=["snapshot", "pipeline_version", "input_sha256"],
            name="unique_snapshot_text_pipeline_input")]


class EvidenceTextExtractionDisabled(Exception):
    pass


class EvidenceTextExtractionNotAllowed(Exception):
    pass


class OCRUnavailable(RuntimeError):
    pass


class _ReadableHTML(HTMLParser):
    _ignored = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._ignored:
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._ignored and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)


def extract_html(content: bytes) -> tuple[str, str]:
    parser = _ReadableHTML()
    parser.feed(content.decode("utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return text, "stdlib-htmlparser"


def extract_image_ocr(content: bytes, language: str) -> tuple[str, str]:
    try:
        from PIL import Image
        import pytesseract
        from io import BytesIO
    except ImportError as exc:
        raise OCRUnavailable("Local image OCR requires optional Pillow and pytesseract dependencies.") from exc
    text = pytesseract.image_to_string(Image.open(BytesIO(content)), lang=language or None)
    return re.sub(r"\s+", " ", text).strip(), f"pytesseract-{pytesseract.get_tesseract_version()}"


def extract_pdf_ocr(content: bytes, language: str) -> tuple[str, str]:
    try:
        import fitz
        import pytesseract
        from PIL import Image
        from io import BytesIO
    except ImportError as exc:
        raise OCRUnavailable(
            "Local PDF OCR requires optional PyMuPDF, Pillow and pytesseract dependencies.") from exc
    document = fitz.open(stream=content, filetype="pdf")
    pages = []
    for page in document:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        pages.append(pytesseract.image_to_string(image, lang=language or None))
    text = re.sub(r"\s+", " ", "\n".join(pages)).strip()
    return text, f"pymupdf-{fitz.VersionBind}+pytesseract-{pytesseract.get_tesseract_version()}"


def extract_snapshot_text(
    snapshot: EvidenceSnapshot, *, language: str = "pol",
    storage: SnapshotStorage | None = None, pipeline_version: str = PIPELINE_VERSION,
    image_ocr=extract_image_ocr, pdf_ocr=extract_pdf_ocr,
) -> EvidenceTextExtraction:
    """Extract text once for this snapshot/version/hash, recording failures safely."""
    if not getattr(settings, "EVIDENCE_TEXT_EXTRACTION_ENABLED", False):
        raise EvidenceTextExtractionDisabled("Evidence text extraction is disabled by default.")
    if snapshot.consent_status != SnapshotConsentStatus.ALLOWED:
        raise EvidenceTextExtractionNotAllowed(
            "Text extraction requires the snapshot consent status to be explicitly allowed.")
    if SnapshotAllowedUse.TEXT_EXTRACTION not in (snapshot.allowed_uses or []):
        raise EvidenceTextExtractionNotAllowed(
            "Text extraction is not included in this snapshot's explicit allowed uses.")

    content = (storage or get_snapshot_storage()).get(snapshot.storage_key)
    digest = sha256(content).hexdigest()
    method = {
        SnapshotArtifactType.HTML: "html",
        SnapshotArtifactType.IMAGE: "image_ocr",
        SnapshotArtifactType.PDF: "pdf_ocr",
    }.get(snapshot.artifact_type, "unsupported")
    result, created = EvidenceTextExtraction.objects.get_or_create(
        snapshot=snapshot, pipeline_version=pipeline_version, input_sha256=digest,
        defaults={"article": snapshot.article, "method": method, "language": language})
    if not created:
        return result

    try:
        if digest != snapshot.content_sha256:
            raise ValueError("Stored artifact hash does not match snapshot metadata.")
        if method == "html":
            text, engine = extract_html(content)
        elif method == "image_ocr":
            text, engine = image_ocr(content, language)
        elif method == "pdf_ocr":
            text, engine = pdf_ocr(content, language)
        else:
            raise ValueError(f"Unsupported snapshot artifact type: {snapshot.artifact_type}")
        result.text = text
        result.text_sha256 = sha256(text.encode("utf-8")).hexdigest()
        result.engine_version = str(engine)
        result.status = EvidenceExtractionStatus.SUCCEEDED
    except Exception as exc:  # failure is data: retain it for review/retry under a new version
        result.status = EvidenceExtractionStatus.FAILED
        result.error = f"{type(exc).__name__}: {exc}"[:4000]
    result.processed_at = timezone.now()
    result.save(update_fields=[
        "text", "text_sha256", "engine_version", "status", "error", "processed_at"])
    return result
