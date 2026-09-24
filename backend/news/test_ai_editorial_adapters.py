from datetime import date

import pytest

from news.ai_editorial import EditorialProposalRequest, EmbeddingRequest, EligibleEvidence, RerankRequest, make_evidence_packet
from news.ai_editorial_adapters import (EditorialProviderDisabledError, EditorialProviderError,
                                        GroqEditorialProposalProvider, NIMEditorialProvider)


def packet():
    return make_evidence_packet([EligibleEvidence(
        material_id="article-1", public_url="https://example.org/material", source_name="Źródło",
        published_on=date(2026, 9, 22), excerpt="Krótki fragment do sprawdzenia", quote="Cytowany fragment",
        source_allowed_uses=frozenset({"ai_draft_metadata"}))])


def test_disabled_providers_never_make_network_calls(monkeypatch):
    monkeypatch.setattr("news.ai_editorial_adapters.requests.post", lambda *a, **k: pytest.fail("network"))
    monkeypatch.delenv("NIM_ENABLED", raising=False)
    monkeypatch.delenv("GROQ_EDITORIAL_ENABLED", raising=False)
    with pytest.raises(EditorialProviderDisabledError):
        NIMEditorialProvider.from_environment()
    with pytest.raises(EditorialProviderDisabledError):
        GroqEditorialProposalProvider.from_environment()


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_nim_payload_is_minimized_and_results_are_mapped(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return Response({"data": [{"index": 0, "embedding": [0.1, 0.2]}]})
    monkeypatch.setattr("news.ai_editorial_adapters.requests.post", post)
    provider = NIMEditorialProvider("key", "embed-model", "rerank-model", rerank_url="https://nim.example/rerank")
    result = provider.embed(EmbeddingRequest(packet(), "embed-model"))
    assert result[0].material_id == "article-1"
    sent = calls[0][1]["input"][0]
    assert "https://" not in sent and "Cytowany fragment" not in sent


def test_nim_reranking_requires_complete_safe_positions(monkeypatch):
    monkeypatch.setattr("news.ai_editorial_adapters.requests.post", lambda *a, **k: Response({"rankings": []}))
    provider = NIMEditorialProvider("key", "embed-model", "rerank-model", rerank_url="https://nim.example/rerank")
    with pytest.raises(EditorialProviderError):
        provider.rerank(RerankRequest("pytanie", packet(), "rerank-model"))


def test_groq_payload_only_has_packet_evidence_and_validates_response(monkeypatch):
    captured = {}
    good = {"schema_version": "editorial-proposal-v1", "status": "pending_review", "title": "Do oceny",
            "claim": "Pytanie", "citations": [{"material_id": "article-1", "public_url": "https://example.org/material", "quote": "Cytowany fragment"}],
            "evidence_for": ["article-1"], "evidence_against": [], "gaps": ["Brak"], "evidence_coverage": 0.5}
    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return Response({"choices": [{"message": {"content": __import__("json").dumps(good)}}]})
    monkeypatch.setattr("news.ai_editorial_adapters.requests.post", post)
    proposal = GroqEditorialProposalProvider("key", "groq-model").propose(EditorialProposalRequest("Pytanie", packet()))
    assert proposal.status == "pending_review"
    user_data = captured["messages"][1]["content"]
    assert "snapshot" not in user_data.lower() and "article-1" in user_data


def test_groq_rejects_unknown_citation_even_when_provider_returns_200(monkeypatch):
    unsafe = {"schema_version": "editorial-proposal-v1", "status": "pending_review", "title": "Do oceny",
              "claim": "Pytanie", "citations": [{"material_id": "other", "public_url": "https://bad.example", "quote": "x"}],
              "evidence_for": ["other"], "evidence_against": [], "gaps": [], "evidence_coverage": 0.5}
    monkeypatch.setattr("news.ai_editorial_adapters.requests.post", lambda *a, **k: Response({"choices": [{"message": {"content": __import__("json").dumps(unsafe)}}]}))
    with pytest.raises(EditorialProviderError):
        GroqEditorialProposalProvider("key", "groq-model").propose(EditorialProposalRequest("Pytanie", packet()))
