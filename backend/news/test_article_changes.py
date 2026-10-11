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


@pytest.mark.django_db
def test_change_flags_mark_changed_and_ignore_rejected():
    from news.article_changes import attach_change_flags, change_flags
    source = Source.objects.create(name="Test", url="https://example.test", source_type="media")
    changed = Article.objects.create(source=source, title="A", url="https://example.test/a")
    rejected = Article.objects.create(source=source, title="B", url="https://example.test/b")
    clean = Article.objects.create(source=source, title="C", url="https://example.test/c")
    for article in (changed, rejected):
        ArticleContent.objects.create(article=article, text="Stara", response_sha256="a", source_url=article.url)
    record_successful_change(article=changed, title="A", body="Nowa")
    ArticleChangeEvent.objects.filter(pk=record_successful_change(article=rejected, title="B", body="Nowa").pk).update(
        status=ArticleChangeEvent.ReviewStatus.REJECTED)
    assert set(change_flags([changed.pk, rejected.pk, clean.pk])) == {changed.pk}
    rows = [{'id': changed.pk}, {'id': clean.pk}]
    attach_change_flags(rows)
    assert rows[0]['text_changed']['content_changed'] is True and rows[1]['text_changed'] is None
