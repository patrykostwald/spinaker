from __future__ import annotations

from hashlib import sha256

from .models import ArticleChangeEvent, ArticleContent


def _digest(value: str) -> str:
    return sha256((value or "").strip().encode("utf-8")).hexdigest()


def record_successful_change(*, article, title: str, body: str, source_status: int | None = None,
                             evidence_snapshot=None) -> ArticleChangeEvent | None:
    """Create a private review event when a known article changes.

    The public Article/ArticleContent rows are intentionally left untouched until
    an editor reviews the event.
    """
    content = ArticleContent.objects.filter(article=article).first()
    if content is None:
        return None
    old_title = _digest(article.title)
    new_title = _digest(title)
    old_body = _digest(content.text)
    new_body = _digest(body) if body else old_body
    if old_title == new_title and old_body == new_body:
        return None
    event, _ = ArticleChangeEvent.objects.get_or_create(
        article=article,
        change_type=ArticleChangeEvent.ChangeType.MODIFIED,
        current_content_sha256=new_body,
        current_title_sha256=new_title,
        defaults={
            "previous_title_sha256": old_title,
            "previous_content_sha256": old_body,
            "source_status": source_status,
            "evidence_snapshot": evidence_snapshot,
            "details": {"title_changed": old_title != new_title, "content_changed": old_body != new_body},
        },
    )
    return event


def record_removed(*, article, source_status: int, evidence_snapshot=None) -> ArticleChangeEvent:
    """Queue a private removal event; never hide or delete the public article."""
    title_hash = _digest(article.title)
    event, _ = ArticleChangeEvent.objects.get_or_create(
        article=article,
        change_type=ArticleChangeEvent.ChangeType.REMOVED,
        current_content_sha256="",
        current_title_sha256=title_hash,
        defaults={
            "previous_title_sha256": title_hash,
            "previous_content_sha256": getattr(getattr(article, "content", None), "response_sha256", ""),
            "source_status": source_status,
            "evidence_snapshot": evidence_snapshot,
            "details": {"reason": "publisher_removed_or_withheld", "public_article_unchanged": True},
        },
    )
    return event


def change_flags(article_ids) -> dict[int, dict]:
    """F2 (strażnik cytatu): materiały, których treść lub tytuł zmieniły się po zapisaniu u nas albo które zniknęły.

    Pokazujemy tylko fakt i datę wykrycia (z haszy, bez treści); odrzucone przez redakcję zdarzenia pomijamy.
    """
    ids = [pk for pk in article_ids if pk]
    if not ids:
        return {}
    flags = {}
    events = (ArticleChangeEvent.objects.filter(article_id__in=ids)
              .exclude(status=ArticleChangeEvent.ReviewStatus.REJECTED).order_by('detected_at'))
    for event in events:
        flags[event.article_id] = {
            'type': event.change_type, 'detected_at': event.detected_at,
            'title_changed': bool(event.details.get('title_changed')), 'content_changed': bool(event.details.get('content_changed')),
        }
    return flags


def attach_change_flags(rows) -> None:
    """Dopisuje `text_changed` (dict albo None) do listy materiałów z kluczem `id` = id artykułu."""
    flags = change_flags([row.get('id') for row in rows])
    for row in rows:
        row['text_changed'] = flags.get(row.get('id'))
