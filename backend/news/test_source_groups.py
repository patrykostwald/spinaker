import pytest

from news.models import Source
from news.serializers import SourceSerializer
from news.source_groups import TOP_MEDIA, portal_group


@pytest.mark.django_db
def test_portal_group_classifies_top_public_and_media():
    top = Source.objects.create(name="TVN24", url="https://tvn24.pl/najwazniejsze.xml", source_type="portal")
    public = Source.objects.create(name="Ministerstwo Finansów", url="https://www.gov.pl/web/finanse", source_type="institution")
    media = Source.objects.create(name="OKO.press", url="https://oko.press/feed/", source_type="portal")

    assert portal_group(top) == "top"
    assert portal_group(public) == "publiczne"
    assert portal_group(media) == "media"
    assert SourceSerializer(top).data["portal_group"] == "top"


def test_top_media_list_is_balanced_and_small():
    assert len(TOP_MEDIA) == len(set(TOP_MEDIA)) == 12
    assert {"TVN24", "TVP Info", "TV Republika", "Polsat News", "pap.pl"} <= set(TOP_MEDIA)
