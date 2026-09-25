import pytest
from django.utils import timezone

from news.article_changes import record_removed, record_successful_change
from news.models import Article, ArticleChangeEvent, ArticleContent, Source


@pytest.mark.django_db
def test_changed_article_is_queued_without_replacing_public_content():
    source = Source.objects.create(name="Test", url="https://example.test", source_type="media")
    article = Article.objects.create(source=source, title="Stary tytuł", url="https://example.test/a")
    ArticleContent.objects.create(article=article, text="Stara treść", response_sha256="a", source_url=article.url)

    event = record_successful_change(article=article, title="Nowy tytuł", body="Nowa treść", source_status=200)

    assert event.status == ArticleChangeEvent.ReviewStatus.PENDING
    assert article.title == "Stary tytuł"
    assert article.content.text == "Stara treść"


@pytest.mark.django_db
def test_removed_article_is_queued_and_article_remains():
    source = Source.objects.create(name="Test", url="https://example.test", source_type="media")
    article = Article.objects.create(source=source, title="Materiał", url="https://example.test/a")
    event = record_removed(article=article, source_status=404)

    assert event.change_type == ArticleChangeEvent.ChangeType.REMOVED
    assert event.status == ArticleChangeEvent.ReviewStatus.PENDING
    assert Article.objects.filter(pk=article.pk).exists()
