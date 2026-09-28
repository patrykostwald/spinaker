import pytest
from django.core.cache import cache

from news.descriptions import clean_description
from news.models import Article, Source
from news.serializers import ArticleSerializer


LEAD = 'Rząd przedstawił projekt ustawy. Posłowie omówią go na kolejnym posiedzeniu.'


@pytest.mark.parametrize('boilerplate', [
    'Zapraszamy również tutaj: 🔴 Portal Gazeta Wyborcza: https://wyborcza.pl/0,0.html 🔴 Kanał: https://youtube.com/@wyborcza',
    '📢SUBSKRYBUJ NASZ KANAŁ - https://youtube.com/@TelewizjawPolsce24',
    '🔔http://bit.ly/Subskrybuj_TV_Republika - subskrybuj nasz kanał',
    'Zapraszamy do oglądania! Obserwuj nas. Dołącz do nas!',
    'Wspieraj nas na Patronite: https://patronite.pl/redakcja',
    'Kliknij dzwoneczek! Polub/udostępnij!',
    'Więcej na www.example.pl. Czytaj także: https://example.pl/tekst',
    'Facebook: https://facebook.com/redakcja\nInstagram: @redakcja\nTikTok: @redakcja\nX: @redakcja',
    'Portal Gazeta Wyborcza: https://wyborcza.pl/0,0.html',
    '===\n🔴 https://example.pl | www.example.pl\n---',
])
def test_removes_boilerplate_and_preserves_separate_lead(boilerplate):
    assert clean_description(boilerplate) == ''
    assert clean_description(boilerplate + '\n' + LEAD) == LEAD
    assert clean_description(LEAD + '\n' + boilerplate) == LEAD


@pytest.mark.parametrize('text', [
    LEAD,
    'Rząd  przedstawił projekt ustawy.\nPosłowie\t omówią go na kolejnym posiedzeniu.',
    'Rząd przedstawił projekt ustawy.\r\nPosłowie omówią go na kolejnym posiedzeniu.',
])
def test_normal_lead_only_normalizes_whitespace(text):
    assert clean_description(text) == LEAD


@pytest.mark.parametrize('text', [
    'Minister powiedział: zapraszamy do rozmów o projekcie ustawy.',
    'Portal opublikował wyniki badań dotyczących zmian klimatu.',
    'Facebook i Instagram zmieniły zasady publikacji materiałów.',
    'W debacie pojawił się #budżet oraz propozycje zmian podatkowych.',
    'Wynik wyniósł 3,5 proc. — to mniej niż zakładano (5 proc.).',
])
def test_preserves_substantive_mentions(text):
    assert clean_description(text) == text


@pytest.mark.parametrize('url', [
    'https://example.pl/tekst?q=1', 'http://example.pl', 'www.example.pl',
    'bit.ly/abc', 'youtu.be/abc', 't.co/abc', 'tinyurl.com/abc',
])
def test_removes_links_and_empty_separators(url):
    assert clean_description(LEAD + '\n | (' + url + ') | ') == LEAD
    assert clean_description('Szczegóły (' + url + ') projektu ustawy poznamy jutro.') == (
        'Szczegóły projektu ustawy poznamy jutro.'
    )


def test_trailing_hashtags_and_decorations():
    assert clean_description('📢' + LEAD + '\n*****\n#polityka #Sejm') == LEAD


@pytest.mark.parametrize('text,expected', [('', ''), (' ' * 30, ''), ('a' * 24, ''), ('a' * 25, 'a' * 25)])
def test_minimum_content_length(text, expected):
    assert clean_description(text) == expected


@pytest.mark.django_db
@pytest.mark.parametrize('allowed', [True, False])
def test_serializer_cleans_after_media_rights_without_changing_database(allowed, monkeypatch):
    cache.clear()
    source = Source.objects.create(name='Redakcja', url='https://example.pl', source_type='institution' if allowed else 'rss')
    original = '📢SUBSKRYBUJ NASZ KANAŁ - https://youtube.com/@redakcja\n' + LEAD
    article = Article.objects.create(source=source, title='Materiał', url='https://example.pl/tekst', description=original)
    inputs = []

    def tracked_clean(text):
        inputs.append(text)
        return clean_description(text)

    monkeypatch.setattr('news.serializers.clean_description', tracked_clean)
    assert ArticleSerializer(article).data['description'] == (LEAD if allowed else '')
    assert inputs == [original if allowed else '']
    assert article.description == original
    article.refresh_from_db()
    assert article.description == original
