"""Independent development and transparent institutional cooperation."""
import json
from datetime import timedelta
from urllib.parse import urlparse
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from news import agents_common as common
from news.agent_models import AgentNote

TOPICS = ('konkurencja i innowacje fact-checkingu', 'granty i programy UE dla niezależnych mediów',
          'monetyzacja mediów niezależnych', 'zapotrzebowanie instytucji na jawne analizy dezinformacji i FIMI')
SEARCH_SCHEMA = {'type': 'object', 'properties': {'summary': common.TEXT,
    'sources': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'url': common.TEXT, 'title': common.TEXT}, 'required': ['url', 'title']}}}, 'required': ['summary', 'sources']}


def sources(items):
    return [{'url': x['url'][:1000], 'title': str(x.get('title', ''))[:300]} for x in items[:12]
            if isinstance(x, dict) and isinstance(x.get('url'), str)
            and urlparse(x['url']).scheme in ('https', 'http') and urlparse(x['url']).netloc]


def signals():
    from news.clinic_models import SpinDiagnosis, SpinOpinion, ClinicDailyMessage
    from news.models import Thread, PersonalContextThread, ArticleOpinion, ThreadOpinion
    from news.community_models import CommunityThreadOpinion
    since = timezone.now() - timedelta(days=30)
    def opinions(model):
        return list(model.objects.filter(created_at__gte=since).values('polarity').annotate(n=Count('pk')).order_by('polarity'))
    return {'period_days': 30, 'diagnoses': SpinDiagnosis.objects.filter(created_at__gte=since).count(),
        'accounts_total': get_user_model().objects.count(), 'threads_total': Thread.objects.count(),
        'reader_threads_total': PersonalContextThread.objects.count(),
        'opinions': {m.__name__: opinions(m) for m in (SpinOpinion, ArticleOpinion, ThreadOpinion, CommunityThreadOpinion)},
        'comments_count': SpinOpinion.objects.exclude(body='').filter(created_at__gte=since).count(),
        'most_reacted': list(SpinOpinion.objects.filter(created_at__gte=since).values('diagnosis_id')
                            .annotate(n=Count('pk')).order_by('-n')[:10]),
        'themes': list(ClinicDailyMessage.objects.filter(status='approved', created_at__gte=since)
                       .values_list('themes', flat=True)[:14]),
        'views_shares': 'Brak osobnych liczników oglądalności i udostępnień w modelach serwisu.'}


def step(force=False):
    signal = AgentNote.objects.filter(agent='strateg', kind='signal', status='new').first()
    if signal:
        previous = AgentNote.objects.filter(agent='strateg', kind='idea').first()
        return common.proposal('strateg', 'B' if previous and previous.track == 'A' else 'A', signal, force)
    from news.clinic_council import FREE_CHECK
    topic = TOPICS[AgentNote.objects.filter(agent='strateg', kind='signal').count() % len(TOPICS)]
    result = common.ask(FREE_CHECK, 'Wykonaj jedną kwerendę w wyszukiwarce: ' + topic +
                        '. Zwróć zwięzłe sygnały i rzeczywiste URL źródeł. Nie wymyślaj źródeł.',
                        {'topic': topic}, SEARCH_SCHEMA, force)
    if not isinstance(result.get('summary'), str) or not isinstance(result.get('sources'), list):
        raise ValueError('Niepełny zwiad.')
    return AgentNote.objects.create(agent='strateg', kind='signal', title='Zwiad: ' + topic,
        body=json.dumps({'external': result['summary'], 'internal': signals()}, ensure_ascii=False),
        sources=sources(result['sources']))
