"""Provider-neutral, fail-closed contracts for future editorial AI.

This module deliberately has no provider SDK, HTTP client, Django model write,
or settings dependency.  It only accepts a small ``EvidencePacket`` assembled
by an internal caller after consent was checked.  In particular, raw snapshot
bytes, private storage keys and full extracted text are not part of these
contracts.

Future NVIDIA NIM and Groq adapters must implement these interfaces behind an
explicit feature flag and cost limit.  A proposal remains a review-only draft;
this module cannot publish a Thread or change a PoliticalDraft status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Protocol, Sequence
from urllib.parse import urlparse


SCHEMA_VERSION = "editorial-proposal-v1"
RAG_ALLOWED_USE = "rag"
METADATA_ALLOWED_USE = "ai_draft_metadata"
PENDING_REVIEW = "pending_review"


class EvidenceEligibilityError(ValueError):
    """Raised when a caller tries to include material without a usable grant."""


class ProposalValidationError(ValueError):
    """Raised when a provider proposal cannot safely become an editorial draft."""


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@dataclass(frozen=True)
class EligibleEvidence:
    """Minimal, citation-ready evidence; never raw snapshot or full article text."""

    material_id: str
    public_url: str
    source_name: str
    published_on: date
    excerpt: str
    quote: str
    source_allowed_uses: frozenset[str]
    derived_from_snapshot: bool = False
    snapshot_consent_status: str | None = None
    snapshot_allowed_uses: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.material_id or not _is_public_url(self.public_url):
            raise EvidenceEligibilityError("Evidence requires an identifier and public URL.")
        if not self.source_name or not self.excerpt.strip() or not self.quote.strip():
            raise EvidenceEligibilityError("Evidence requires source, short excerpt and quote.")
        if len(self.excerpt) > 1200 or len(self.quote) > 600:
            raise EvidenceEligibilityError("Evidence packet exceeds the short editorial excerpt limit.")
        if self.derived_from_snapshot:
            if self.snapshot_consent_status != "allowed" or RAG_ALLOWED_USE not in self.snapshot_allowed_uses:
                raise EvidenceEligibilityError("Snapshot-derived evidence requires explicit allowed RAG consent.")
        elif METADATA_ALLOWED_USE not in self.source_allowed_uses:
            raise EvidenceEligibilityError("Non-snapshot evidence requires explicit metadata editorial use.")


@dataclass(frozen=True)
class EvidencePacket:
    """Explicit allow-listed input to embedding, reranking and proposal adapters."""

    records: tuple[EligibleEvidence, ...]

    def __post_init__(self) -> None:
        ids = [record.material_id for record in self.records]
        if not ids or len(ids) != len(set(ids)):
            raise EvidenceEligibilityError("Evidence packet needs at least one uniquely identified record.")


def make_evidence_packet(records: Sequence[EligibleEvidence]) -> EvidencePacket:
    """Build an explicit packet.  Callers cannot pass raw snapshots by accident."""
    return EvidencePacket(records=tuple(records))


@dataclass(frozen=True)
class EmbeddingRequest:
    packet: EvidencePacket
    model_version: str


@dataclass(frozen=True)
class EmbeddingResult:
    material_id: str
    vector: tuple[float, ...]
    model_version: str


@dataclass(frozen=True)
class RerankRequest:
    query: str
    packet: EvidencePacket
    model_version: str


@dataclass(frozen=True)
class RerankResult:
    material_id: str
    score: float
    model_version: str


@dataclass(frozen=True)
class EditorialProposalRequest:
    question: str
    packet: EvidencePacket
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class Citation:
    material_id: str
    public_url: str
    quote: str


@dataclass(frozen=True)
class EditorialProposal:
    """A structured, non-publishable candidate for human review."""

    schema_version: str
    status: str
    title: str
    claim: str
    citations: tuple[Citation, ...]
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]
    gaps: tuple[str, ...]
    evidence_coverage: float


class EmbeddingProvider(Protocol):
    def embed(self, request: EmbeddingRequest) -> tuple[EmbeddingResult, ...]: ...


class RerankingProvider(Protocol):
    def rerank(self, request: RerankRequest) -> tuple[RerankResult, ...]: ...


class EditorialProposalProvider(Protocol):
    def propose(self, request: EditorialProposalRequest) -> EditorialProposal: ...


class FakeEmbeddingProvider:
    """Deterministic test double.  It never performs network or database I/O."""

    def embed(self, request: EmbeddingRequest) -> tuple[EmbeddingResult, ...]:
        def vector(record: EligibleEvidence) -> tuple[float, ...]:
            digest = sha256((record.material_id + record.excerpt).encode()).digest()
            return tuple(round(byte / 255, 6) for byte in digest[:4])
        return tuple(EmbeddingResult(record.material_id, vector(record), request.model_version)
                     for record in request.packet.records)


class FakeRerankingProvider:
    """Deterministic test double; lexical overlap is sufficient for contract tests."""

    def rerank(self, request: RerankRequest) -> tuple[RerankResult, ...]:
        terms = {term.casefold() for term in request.query.split() if term}
        ranked = [RerankResult(record.material_id,
                  float(len(terms & set((record.excerpt + " " + record.quote).casefold().split()))),
                  request.model_version) for record in request.packet.records]
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.material_id)))


class FakeEditorialProposalProvider:
    """Creates a deliberately conservative pending-review fixture proposal."""

    def propose(self, request: EditorialProposalRequest) -> EditorialProposal:
        first = request.packet.records[0]
        return EditorialProposal(
            schema_version=request.schema_version, status=PENDING_REVIEW,
            title="Propozycja do sprawdzenia", claim=request.question,
            citations=(Citation(first.material_id, first.public_url, first.quote),),
            evidence_for=(first.material_id,), evidence_against=(),
            gaps=("Wymaga oceny redaktora.",), evidence_coverage=0.5)


def validate_proposal(proposal: EditorialProposal, packet: EvidencePacket) -> EditorialProposal:
    """Accept only citation-complete, review-only proposals tied to this packet."""
    if proposal.schema_version != SCHEMA_VERSION:
        raise ProposalValidationError("Proposal has an unsupported schema version.")
    if proposal.status != PENDING_REVIEW:
        raise ProposalValidationError("AI proposals may only be pending review; publication is forbidden.")
    if not proposal.title.strip() or not proposal.claim.strip():
        raise ProposalValidationError("Proposal requires a title and a claim for review.")
    if not 0 <= proposal.evidence_coverage <= 1:
        raise ProposalValidationError("Evidence coverage must be between zero and one.")
    allowed = {record.material_id: record for record in packet.records}
    referenced = set(proposal.evidence_for) | set(proposal.evidence_against)
    if not referenced <= set(allowed):
        raise ProposalValidationError("Proposal references material outside the evidence packet.")
    if not proposal.citations:
        raise ProposalValidationError("Proposal requires at least one citation.")
    for citation in proposal.citations:
        record = allowed.get(citation.material_id)
        if record is None or not citation.public_url or citation.public_url != record.public_url:
            raise ProposalValidationError("Every citation needs the matching public URL from the packet.")
        if not citation.quote.strip():
            raise ProposalValidationError("Every citation requires a quote.")
    return proposal
