from hashlib import sha256

import pytest

from news.evidence_extraction import (
    EvidenceExtractionStatus,
    EvidenceTextExtraction,
    EvidenceTextExtractionDisabled,
    EvidenceTextExtractionNotAllowed,
    extract_snapshot_text,
)
from news.evidence_snapshot import EvidenceSnapshot, SnapshotConsentStatus
from news.models import Article, Source
from news.snapshot_storage import LocalFileSnapshotStorage


@pytest.fixture
def article(db):
    source = Source.objects.create(name="OCR source", url="https://example.org")
    return Article.objects.create(source=source, title="Box", url="https://example.org/a")


@pytest.fixture
def storage(tmp_path):
    return LocalFileSnapshotStorage(tmp_path / "private")


def make_snapshot(article, storage, content, artifact_type="html", consent="allowed",
                  allowed_uses=("text_extraction",)):
    digest = sha256(content).hexdigest()
    key = f"{article.pk}/{artifact_type}/{digest}"
    storage.put(key, content)
    return EvidenceSnapshot.objects.create(
        article=article, source_url=article.url, content_sha256=digest,
        artifact_type=artifact_type, parser_version="capture-v1",
        consent_status=consent, allowed_uses=list(allowed_uses), storage_key=key)


def test_pipeline_is_disabled_by_default(article, storage, settings):
    snapshot = make_snapshot(article, storage, b"<p>secret</p>")
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = False
    with pytest.raises(EvidenceTextExtractionDisabled):
        extract_snapshot_text(snapshot, storage=storage)
    assert EvidenceTextExtraction.objects.count() == 0


@pytest.mark.parametrize("consent", ["unknown", "restricted", "denied"])
def test_only_explicitly_allowed_snapshots_are_processed(article, storage, settings, consent):
    snapshot = make_snapshot(article, storage, b"<p>secret</p>", consent=consent)
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    with pytest.raises(EvidenceTextExtractionNotAllowed):
        extract_snapshot_text(snapshot, storage=storage)
    assert EvidenceTextExtraction.objects.count() == 0


def test_allowed_storage_without_text_scope_is_not_processed(article, storage, settings):
    snapshot = make_snapshot(article, storage, b"<p>secret</p>", allowed_uses=())
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    with pytest.raises(EvidenceTextExtractionNotAllowed):
        extract_snapshot_text(snapshot, storage=storage)
    assert EvidenceTextExtraction.objects.count() == 0


def test_html_is_deterministic_and_linked_to_snapshot_and_box(article, storage, settings):
    snapshot = make_snapshot(
        article, storage,
        b"<html><style>hide</style><article><h1>Title</h1><p>Body &amp; more</p>"
        b"<script>ignore()</script></article></html>")
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    result = extract_snapshot_text(snapshot, storage=storage, language="pl")
    assert result.status == EvidenceExtractionStatus.SUCCEEDED
    assert result.snapshot == snapshot and result.article == article
    assert result.method == "html"
    assert result.text == "Title Body & more"
    assert result.text_sha256 == sha256(result.text.encode()).hexdigest()
    assert result.language == "pl"
    assert result.processed_at is not None


def test_same_snapshot_version_and_input_is_idempotent(article, storage, settings):
    snapshot = make_snapshot(article, storage, b"<p>Once</p>")
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    first = extract_snapshot_text(snapshot, storage=storage)
    second = extract_snapshot_text(snapshot, storage=storage)
    assert first.pk == second.pk
    assert EvidenceTextExtraction.objects.count() == 1


@pytest.mark.parametrize("artifact_type, expected_method", [
    ("image", "image_ocr"), ("pdf", "pdf_ocr")])
def test_binary_artifacts_use_ocr_adapter(article, storage, settings, artifact_type, expected_method):
    snapshot = make_snapshot(article, storage, b"binary", artifact_type=artifact_type)
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    calls = []

    def local_ocr(content, language):
        calls.append((content, language))
        return "Recognized text", "fake-local-1"

    result = extract_snapshot_text(
        snapshot, storage=storage, image_ocr=local_ocr, pdf_ocr=local_ocr)
    assert result.status == EvidenceExtractionStatus.SUCCEEDED
    assert result.method == expected_method
    assert calls == [(b"binary", "pol")]


def test_missing_optional_ocr_is_recorded_as_failure(article, storage, settings):
    snapshot = make_snapshot(article, storage, b"image", artifact_type="image")
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True

    def unavailable(content, language):
        raise ImportError("optional OCR is absent")

    result = extract_snapshot_text(snapshot, storage=storage, image_ocr=unavailable)
    assert result.status == EvidenceExtractionStatus.FAILED
    assert "optional OCR is absent" in result.error
    assert result.text == ""


def test_changed_storage_bytes_fail_hash_verification(article, storage, settings):
    snapshot = make_snapshot(article, storage, b"original")
    other = LocalFileSnapshotStorage(storage.root.parent / "tampered")
    other.put(snapshot.storage_key, b"tampered")
    settings.EVIDENCE_TEXT_EXTRACTION_ENABLED = True
    result = extract_snapshot_text(snapshot, storage=other)
    assert result.status == EvidenceExtractionStatus.FAILED
    assert "hash does not match" in result.error
