from datetime import date

import pytest

from news.ai_editorial import (
    Citation, EditorialProposal, EditorialProposalRequest, EmbeddingRequest,
    EvidenceEligibilityError, EligibleEvidence, FakeEditorialProposalProvider,
    FakeEmbeddingProvider, FakeRerankingProvider, ProposalValidationError,
    RerankRequest, SCHEMA_VERSION, make_evidence_packet, validate_proposal)


def evidence(*, derived=False, snapshot_uses=frozenset(), source_uses=frozenset({"ai_draft_metadata"}),
             snapshot_consent=None):
    return EligibleEvidence(
        material_id="article-1", public_url="https://example.org/material", source_name="Źródło",
        published_on=date(2026, 9, 22), excerpt="Krótki fragment do sprawdzenia", quote="Cytowany fragment",
        source_allowed_uses=source_uses, derived_from_snapshot=derived,
        snapshot_consent_status=("allowed" if derived else None) if snapshot_consent is None else snapshot_consent,
        snapshot_allowed_uses=snapshot_uses)


def test_snapshot_derived_evidence_is_fail_closed_without_allowed_rag_use():
    with pytest.raises(EvidenceEligibilityError):
        evidence(derived=True)
    with pytest.raises(EvidenceEligibilityError):
        evidence(derived=True, snapshot_uses=frozenset({"rag"}), snapshot_consent="restricted")


def test_non_snapshot_evidence_needs_explicit_metadata_permission():
    with pytest.raises(EvidenceEligibilityError):
        evidence(source_uses=frozenset())


def test_fake_adapters_are_deterministic_and_only_accept_explicit_packet():
    packet = make_evidence_packet([evidence()])
    embeddings = FakeEmbeddingProvider().embed(EmbeddingRequest(packet, "fake-embed-v1"))
    ranking = FakeRerankingProvider().rerank(RerankRequest("fragment", packet, "fake-rerank-v1"))
    proposal = FakeEditorialProposalProvider().propose(EditorialProposalRequest("Czy to prawda?", packet))
    assert embeddings[0].vector == FakeEmbeddingProvider().embed(EmbeddingRequest(packet, "fake-embed-v1"))[0].vector
    assert ranking[0].material_id == "article-1"
    assert validate_proposal(proposal, packet).status == "pending_review"


def test_validator_rejects_unknown_material_missing_url_schema_or_publication():
    packet = make_evidence_packet([evidence()])
    valid = FakeEditorialProposalProvider().propose(EditorialProposalRequest("Pytanie", packet))
    with pytest.raises(ProposalValidationError):
        validate_proposal(EditorialProposal("wrong", "pending_review", "T", "C", valid.citations, (), (), (), .2), packet)
    with pytest.raises(ProposalValidationError):
        validate_proposal(EditorialProposal(SCHEMA_VERSION, "published", "T", "C", valid.citations, (), (), (), .2), packet)
    with pytest.raises(ProposalValidationError):
        validate_proposal(EditorialProposal(SCHEMA_VERSION, "pending_review", "T", "C",
            (Citation("unknown", "https://example.org/x", "cytat"),), ("unknown",), (), (), .2), packet)
    with pytest.raises(ProposalValidationError):
        validate_proposal(EditorialProposal(SCHEMA_VERSION, "pending_review", "T", "C",
            (Citation("article-1", "", "cytat"),), ("article-1",), (), (), .2), packet)
