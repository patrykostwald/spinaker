import pytest
from django.core.exceptions import ValidationError

from news.models import Source, SourceThumbnailPolicy


@pytest.mark.django_db
def test_allowed_thumbnail_requires_license_and_attribution():
    source = Source.objects.create(name='Official', url='https://official.example')
    policy = SourceThumbnailPolicy(
        source=source, status=SourceThumbnailPolicy.Status.ALLOWED,
        terms_url='https://official.example/terms', reviewed_by='test',
        evidence={'review': 'test fixture'})

    with pytest.raises(ValidationError):
        policy.full_clean()

    policy.license_url = 'https://official.example/licence'
    policy.attribution_template = 'Autor — źródło'
    policy.full_clean()
