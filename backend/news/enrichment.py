"""Fill absent publisher metadata only, with an explicit observation trail."""
from django.db import transaction
from django.utils import timezone
from news.models import Article
from news.signals import invalidate_search
from scraper.utils import safe_url


def fill_missing_thumbnail(article_id, metadata, source_url, response_sha256):
    image_url = safe_url(metadata.get('image_url'))
    image_source = metadata.get('image_source')
    if (not image_url or len(image_url) > 1024
            or image_source not in ('meta:og:image', 'meta:twitter:image')):
        return False
    with transaction.atomic():
        article = Article.objects.select_for_update().filter(pk=article_id).first()
        if (article is None or article.image_url or article.category_reviewed
                or article.ingestion_method not in ('rss', 'archive') or article.url != source_url):
            return False
        observed = timezone.now().isoformat()
        observation = (f'Uzupełniono brakującą miniaturę ({observed}): {image_source} = '
            f'{image_url}; źródło: {source_url}; SHA-256 odpowiedzi: {response_sha256}.')
        changed = Article.objects.filter(pk=article.pk, image_url='', category_reviewed=False).update(
            image_url=image_url, evidence_note=(article.evidence_note + '\n' + observation).strip())
        if changed:
            transaction.on_commit(invalidate_search)
        return bool(changed)
