from hashlib import sha256

import pytest

from news.evidence_snapshot import (
    EvidenceSnapshotDisabled,
    SnapshotConsentStatus,
    SnapshotAllowedUse,
    SnapshotRetentionPolicy,
    capture_snapshot,
)
from news.models import Article, EvidenceSnapshot, FetchAttempt, Source, SourceAccessInstruction
from news.snapshot_storage import LocalFileSnapshotStorage


@pytest.fixture
def article(db):
    source = Source.objects.create(name="Test source", url="https://example.org")
    return Article.objects.create(source=source, title="Box", url="https://example.org/a")


@pytest.fixture
def local_storage(tmp_path):
    return LocalFileSnapshotStorage(tmp_path / "evidence")


@pytest.fixture
def successful_fetch(article):
    instruction = SourceAccessInstruction.objects.create(
        source=article.source, version=1, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.HTML,
        allowed_scope=SourceAccessInstruction.Scope.SNAPSHOT,
        endpoint="https://example.org/", terms_url="https://example.org/terms",
        evidence={"basis": "test"}, reviewed_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
        reviewed_by="test",
    )
    return FetchAttempt.objects.create(
        source=article.source, instruction=instruction, instruction_version=instruction.version,
        channel=instruction.channel, requested_kind=FetchAttempt.RequestedKind.PAGE,
        url_fingerprint="a" * 64, url_host="example.org", outcome=FetchAttempt.Outcome.OK,
        network_started=True, http_status=200,
    )


def test_capture_is_disabled_by_default(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = False
    with pytest.raises(EvidenceSnapshotDisabled):
        capture_snapshot(
            article, source_url=article.url, content=b"<html></html>",
            artifact_type="html", parser_version="v1", fetch_attempt=successful_fetch, storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_capture_stores_metadata_separately_from_bytes(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    snapshot = capture_snapshot(
        article, source_url=article.url, content=b"<html>evidence</html>",
        artifact_type="html", parser_version="parser-v1",
        consent_status=SnapshotConsentStatus.RESTRICTED,
        allowed_uses=[SnapshotAllowedUse.TEXT_EXTRACTION],
        retention_policy=SnapshotRetentionPolicy.EVIDENCE_HOLD,
        fetch_attempt=successful_fetch,
        storage=local_storage,
    )
    assert snapshot.article_id == article.pk
    assert snapshot.fetch_attempt_id == successful_fetch.pk
    assert snapshot.source_url == article.url
    assert snapshot.artifact_type == "html"
    assert snapshot.parser_version == "parser-v1"
    assert snapshot.consent_status == SnapshotConsentStatus.RESTRICTED
    assert snapshot.allowed_uses == [SnapshotAllowedUse.TEXT_EXTRACTION]
    assert snapshot.content_sha256 == sha256(b"<html>evidence</html>").hexdigest()
    # The row never carries the bytes; they live only in the storage backend.
    assert local_storage.get(snapshot.storage_key) == b"<html>evidence</html>"
    for field in ("content", "bytes", "binary", "body"):
        assert not hasattr(snapshot, field)


def test_capture_refuses_denied_consent(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    with pytest.raises(ValueError):
        capture_snapshot(
            article, source_url=article.url, content=b"x", artifact_type="image",
            parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.DENIED,
            storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_capture_refuses_unknown_consent(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    with pytest.raises(ValueError):
        capture_snapshot(
            article, source_url=article.url, content=b"x", artifact_type="image",
            parser_version="v1", fetch_attempt=successful_fetch, storage=local_storage)
    assert EvidenceSnapshot.objects.count() == 0


def test_capture_refuses_a_fetch_that_did_not_succeed(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    successful_fetch.outcome = FetchAttempt.Outcome.HTTP_ERROR
    # Build a distinct immutable receipt instead of altering the original one.
    rejected = FetchAttempt.objects.create(
        source=article.source, instruction=successful_fetch.instruction,
        instruction_version=successful_fetch.instruction.version,
        channel=successful_fetch.channel, requested_kind=FetchAttempt.RequestedKind.PAGE,
        url_fingerprint="b" * 64, url_host="example.org",
        outcome=FetchAttempt.Outcome.HTTP_ERROR, network_started=True, http_status=503,
    )
    with pytest.raises(ValueError, match="successful"):
        capture_snapshot(
            article, source_url=article.url, content=b"x", artifact_type="html",
            parser_version="v1", fetch_attempt=rejected,
            consent_status=SnapshotConsentStatus.RESTRICTED, storage=local_storage)


def test_repeated_capture_of_identical_content_shares_storage_key(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    first = capture_snapshot(
        article, source_url=article.url, content=b"same bytes", artifact_type="html",
        parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    second = capture_snapshot(
        article, source_url=article.url, content=b"same bytes", artifact_type="html",
        parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    # Same content re-captured re-uses the same storage key (idempotent put)
    # but still records a distinct evidentiary row with its own fetch time.
    assert first.storage_key == second.storage_key
    assert first.pk != second.pk


def test_capture_defaults_to_no_allowed_uses(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    snapshot = capture_snapshot(
        article, source_url=article.url, content=b"scope", artifact_type="html",
        parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.ALLOWED,
        storage=local_storage)
    assert snapshot.allowed_uses == []


def test_capture_rejects_unknown_allowed_use(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    with pytest.raises(ValueError, match="unknown use"):
        capture_snapshot(
            article, source_url=article.url, content=b"scope", artifact_type="html",
        parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.ALLOWED,
            allowed_uses=["anything_goes"], storage=local_storage)


def test_public_thumbnail_and_private_snapshot_stay_separate(article, successful_fetch, settings, local_storage):
    settings.EVIDENCE_SNAPSHOT_ENABLED = True
    article.image_url = "https://example.org/thumbnail.jpg"
    article.save(update_fields=["image_url"])
    capture_snapshot(
        article, source_url=article.url, content=b"<html></html>", artifact_type="html",
        parser_version="v1", fetch_attempt=successful_fetch, consent_status=SnapshotConsentStatus.ALLOWED, storage=local_storage)
    article.refresh_from_db()
    assert article.image_url == "https://example.org/thumbnail.jpg"
    assert article.evidence_snapshots.count() == 1
    assert article.evidence_snapshots.first().storage_key != article.image_url
