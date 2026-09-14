from hashlib import sha256

import pytest

from news.evidence_snapshot import (
    EvidenceSnapshotDisabled,
    SnapshotConsentStatus,
    SnapshotRetentionPolicy,
    capture_snapshot,
)
from news.models import Article, EvidenceSnapshot, Source
from news.snapshot_storage import LocalFileSnapshotStorage


@pytest.fixture
def article(db):
    source = Source.objects.create(name="Test source", url="https://example.org")
    return Article.objects.create(source=source, title="Box", url="https://example.org/a")


@pytest.fixture
def local_storage(tmp_path):
    return LocalFileSnapshotStorage(tmp_path / "evidence")


def test_capture_is_disabled_by_default(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = False
    with pytest.raises(EvidenceSnapshotDisabled):
        capture_snapshot(
            article, source_url=article.url, content=b"<html></html>",
            artifact_type="html", parser_version="v1", storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_capture_stores_metadata_separately_from_bytes(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    snapshot = capture_snapshot(
        article, source_url=article.url, content=b"<html>evidence</html>",
        artifact_type="html", parser_version="parser-v1",
        consent_status=SnapshotConsentStatus.RESTRICTED,
        retention_policy=SnapshotRetentionPolicy.EVIDENCE_HOLD,
        storage=local_storage,
    )
    assert snapshot.article_id == article.pk
    assert snapshot.source_url == article.url
    assert snapshot.artifact_type == "html"
    assert snapshot.parser_version == "parser-v1"
    assert snapshot.consent_status == SnapshotConsentStatus.RESTRICTED
    assert snapshot.content_sha256 == sha256(b"<html>evidence</html>").hexdigest()
    # The row never carries the bytes; they live only in the storage backend.
    assert local_storage.get(snapshot.storage_key) == b"<html>evidence</html>"
    for field in ("content", "bytes", "binary", "body"):
        assert not hasattr(snapshot, field)


def test_capture_refuses_denied_consent(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    with pytest.raises(ValueError):
        capture_snapshot(
            article, source_url=article.url, content=b"x", artifact_type="image",
            parser_version="v1", consent_status=SnapshotConsentStatus.DENIED,
            storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_capture_refuses_unknown_consent(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    with pytest.raises(ValueError):
        capture_snapshot(
            article, source_url=article.url, content=b"x", artifact_type="image",
            parser_version="v1", storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_repeated_capture_of_identical_content_shares_storage_key(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    first = capture_snapshot(
        article, source_url=article.url, content=b"same bytes", artifact_type="html",
        parser_version="v1", consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    second = capture_snapshot(
        article, source_url=article.url, content=b"same bytes", artifact_type="html",
        parser_version="v1", consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    # Same content re-captured re-uses the same storage key (idempotent put)
    # but still records a distinct evidentiary row with its own fetch time.
    assert first.storage_key == second.storage_key
    assert first.pk != second.pk


def test_public_thumbnail_and_private_snapshot_stay_separate(article, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    article.image_url = "https://example.org/thumbnail.jpg"
    article.save(update_fields=["image_url"])
    capture_snapshot(
        article, source_url=article.url, content=b"<html></html>", artifact_type="html",
        parser_version="v1", consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    article.refresh_from_db()
    assert article.image_url == "https://example.org/thumbnail.jpg"
    assert article.evidence_snapshots.count() == 1
    assert article.evidence_snapshots.first().storage_key != article.image_url
