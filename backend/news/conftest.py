import pytest


@pytest.fixture(autouse=True)
def zakaz_sieci(monkeypatch):
    """Testy nigdy nie wychodzą w sieć (7.10: test podglądu social wołał żywe Gemini, bo klucz był w środowisku powłoki).
    Blokada na poziomie adaptera requests: biblioteka `responses` (@responses.activate) nadal działa, bo podmienia ten sam adapter;
    testy mockujące `requests.get` albo `Session.request` też nie dochodzą do tego miejsca. Błąd to ConnectionError, czyli to samo,
    co kod widzi bez sieci - ścieżki „dostawca nie odpowiada” zachowują się jak na produkcji bez połączenia."""
    import requests
    from unittest.mock import Mock
    monkeypatch.setattr('requests.adapters.HTTPAdapter.send', Mock(side_effect=requests.ConnectionError('Zakaz sieci w testach')))


@pytest.fixture
def auto_approve_threads(monkeypatch):
    """For tests of thread builders and views (not of the review gate itself): every Dr. Spin thread
    passes the publication review at once, with mocked reviewers and no model calls."""
    from news import thread_review as reviews

    def accepted(role, data):
        if role == reviews.EDITOR_STEP:
            return {'title': data['texts']['title'], 'description': data['texts']['description'], 'reason': 'Bez zmian.'}, 'mock:editor'
        if role == reviews.LINGUIST_STEP:
            return {'texts': dict(data['texts']), 'reason': 'Bez zmian.'}, 'mock:linguist'
        return {**{k: True for k in reviews.CHECKS}, 'reason': 'Pokrycie w danych.'}, 'mock:reviewer'

    original = reviews.enqueue

    def enqueue_and_review(thread, evidence):
        review = original(thread, evidence)
        reviews.review_one(review.pk)
        thread.refresh_from_db()
        return review

    monkeypatch.setattr(reviews, 'ask', accepted)
    monkeypatch.setattr(reviews, 'enqueue', enqueue_and_review)
