"""Kanały RSS ściany, tematu i osoby: tytuł, autor, data i link do boxa w spina3 (bez pełnej treści wpisów;
zasady X do potwierdzenia). Powrót bez konta i bez śledzenia; oficjalna droga dla robotów.
W czasie ciszy wyborczej kanał jest wstrzymany (jeden wpis informacyjny, bez pozycji)."""
from __future__ import annotations

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.http import Http404
from django.utils import timezone

from .config import config, election_silence
from .models import Box
from .ranking import wall_boxes


class WallFeed(Feed):
    title = 'spina3: ściana'
    description = 'Wpisy polityków, diagnozy i dokumenty z jednej bazy. Kolor spinki to stanowiska czytelników, nie ocena prawdziwości.'

    def link(self):
        return getattr(settings, 'SPINA3_PUBLIC_URL', 'https://spina3.pl') + '/'

    def items(self):
        if election_silence()['active']:
            return []
        return list(wall_boxes(config().default_period_days).order_by('-published_at')[:50])

    def item_title(self, item: Box):
        return item.title if item.show_title else item.source_name

    def item_description(self, item: Box):
        who = item.author_name or item.source_name
        return f'{who} · {item.get_kind_display()}'

    def item_link(self, item: Box):
        return f"{getattr(settings, 'SPINA3_PUBLIC_URL', 'https://spina3.pl')}/box/{item.pk}/"

    def item_pubdate(self, item: Box):
        return item.published_at

    def item_guid(self, item: Box):
        return f'spina3-box-{item.pk}'

    def feed_extra_kwargs(self, obj):
        return {}

    def get_feed(self, obj, request):
        feed = super().get_feed(obj, request)
        if election_silence()['active']:
            feed.add_item(title='Kanał wstrzymany na czas ciszy wyborczej', link=self.link(),
                          description='Nowe pozycje pojawią się po zakończeniu ciszy wyborczej.', unique_id='spina3-silence',
                          pubdate=timezone.now())
        return feed


class TopicFeed(WallFeed):
    def get_object(self, request, topic):
        if not Box.objects.filter(status='published', topic=topic).exists():
            raise Http404
        return topic

    def title(self, obj):
        return f'spina3: temat {obj}'

    def items(self, obj):
        if election_silence()['active']:
            return []
        return list(wall_boxes(config().default_period_days).filter(topic=obj).order_by('-published_at')[:50])


class PersonFeed(WallFeed):
    def get_object(self, request, person_id):
        return int(person_id)

    def title(self, obj):
        return f'spina3: osoba {obj}'

    def items(self, obj):
        if election_silence()['active']:
            return []
        rows = [b for b in wall_boxes(config().default_period_days).order_by('-published_at')[:500]
                if any(str(p.get('id')) == str(obj) for p in (b.persons or []))]
        return rows[:50]
