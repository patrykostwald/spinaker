import pytest
from rest_framework.test import APIClient
from news.models import Article, Source

pytestmark = pytest.mark.django_db


def test_public_material_links_obey_source_visibility():
    source = Source.objects.create(name='Source', url='https://example.org', is_active=True)
    article = Article.objects.create(source=source, title='Record', url='https://example.org/record')
    client = APIClient()
    assert client.get(f'/api/articles/{article.pk}/').status_code == 200
    source.scrape_enabled = False
    source.save()
    # Stopping an importer does not hide its archive.
    assert client.get(f'/api/articles/{article.pk}/').status_code == 200
    source.is_active = False
    source.save()
    assert client.get(f'/api/articles/{article.pk}/').status_code == 404
    source.is_active = True
    source.catalog_stage = 'excluded'
    source.save()
    assert client.get(f'/api/articles/{article.pk}/').status_code == 404
