from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from news.models import Article, Source, SourceUsageDecision
from news.serializers import ArticleSerializer


def article(url, source_type='rss'):
    source = Source.objects.create(name=url, url=url, is_active=True, source_type=source_type)
    return Article.objects.create(source=source, url=url + '/tekst', title='Tytuł', image_url='https://cdn.example/foto.jpg',
                                  description='Lead artykułu — kilka zdań z portalu.')


@pytest.mark.django_db
def test_press_without_consent_shows_only_title_date_author_link():
    cache.clear()
    data = ArticleSerializer(article('https://www.portal-prasowy.pl')).data
    assert data['title'] == 'Tytuł' and data['url'].endswith('/tekst')
    assert data['image_url'] == '' and data['description'] == ''


@pytest.mark.django_db
@pytest.mark.parametrize('url,source_type', [
    ('https://bip.torun.pl', 'rss'), ('https://www.gov.pl', 'rss'), ('https://www.knf.gov.pl', 'rss'),
    ('https://www.youtube.com/channel/UC123', 'portal'), ('https://ktokolwiek.example', 'institution'),
])
def test_official_and_api_sources_keep_image_and_lead(url, source_type):
    cache.clear()
    data = ArticleSerializer(article(url, source_type)).data
    assert data['image_url'] and data['description']


@pytest.mark.django_db
def test_consent_brings_back_image_and_lead_and_expiry_removes_it():
    cache.clear()
    row = article('https://www.oko.press')
    decision = SourceUsageDecision.objects.create(
        source=row.source, version=1, status='approved', allowed_uses=['public_card'], frozen_host='oko.press',
        applies_until_acquired_at=timezone.now() + timedelta(days=365), terms_url='https://oko.press/zgoda',
        evidence={'mail': 'Zgoda — RSS'}, reviewed_at=timezone.now(), reviewed_by='zespół')
    assert ArticleSerializer(row).data['image_url']
    decision.valid_until = timezone.now() - timedelta(days=1)
    decision.save()
    cache.clear()
    assert ArticleSerializer(row).data['image_url'] == ''
