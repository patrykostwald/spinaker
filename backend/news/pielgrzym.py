"""Research journal for council quality; catalogs are trends, not recruitment."""
import json
import xml.etree.ElementTree as ET
from datetime import timedelta
import requests
from django.db.models import Count, Avg
from django.utils import timezone
from news import agents_common as common
from news.agent_models import AgentNote

TOPICS = ('LLM evaluation', 'multi agent debate', 'language model calibration',
          'language model bias detection', 'multi model critique', 'automated fact checking')


def council_signals():
    from news.clinic_models import CouncilCall, InquisitorReview, SpinDiagnosis
    from news.models import RepairAction
    since = timezone.now() - timedelta(days=30)
    return {'calls': list(CouncilCall.objects.filter(created_at__gte=since).values('provider', 'model', 'outcome')
                         .annotate(n=Count('pk'), seconds=Avg('seconds')).order_by('-n')[:40]),
        'inquisitor': list(InquisitorReview.objects.filter(created_at__gte=since).values('verdict')
                          .annotate(n=Count('pk')).order_by('verdict')),
        'auditor': list(RepairAction.objects.filter(rule__startswith='auditor:', created_at__gte=since)
                        .values('rule', 'result').annotate(n=Count('pk')).order_by('rule', 'result')),
        'agreement': list(SpinDiagnosis.objects.filter(diagnosed_at__gte=since)
                          .values('usage__council__agreement').annotate(n=Count('pk')).order_by('-n')[:20])}


def discover(index):
    found, errors = [], []
    topic = TOPICS[index % len(TOPICS)]
    try:
        response = requests.get('https://export.arxiv.org/api/query', params={
            'search_query': f'all:"{topic}"', 'max_results': 5, 'sortBy': 'submittedDate', 'sortOrder': 'descending'}, timeout=(5, 20))
        response.raise_for_status()
        root = ET.fromstring(response.content)
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('a:entry', ns)[:5]:
            found.append({'title': entry.findtext('a:title', '', ns).strip(),
                'url': entry.findtext('a:id', '', ns), 'summary': entry.findtext('a:summary', '', ns)[:2000]})
    except (requests.RequestException, ET.ParseError) as error:
        errors.append('arXiv: ' + type(error).__name__)
    catalog = ('https://openrouter.ai/api/v1/models' if index % 2 == 0 else
               'https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=5')
    try:
        response = requests.get(catalog, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        items = sorted(data.get('data', []), key=lambda x: x.get('created', 0), reverse=True)[:5] if isinstance(data, dict) else data[:5]
        found.append({'title': 'Katalog modeli — sygnał trendu, bez rekrutacji', 'url': catalog,
                      'summary': ', '.join(str(x.get('id', ''))[:180] for x in items)})
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        errors.append('katalog: ' + type(error).__name__)
    return topic, found, errors


def step(force=False):
    signal = AgentNote.objects.filter(agent='pielgrzym', kind='finding', status='new').first()
    if signal:
        return common.proposal('pielgrzym', '', signal, force)
    common.members(1, force)
    topic, found, errors = discover(AgentNote.objects.filter(agent='pielgrzym', kind='finding').count())
    from news.strateg import sources
    return AgentNote.objects.create(agent='pielgrzym', kind='finding', title='Wędrówka: ' + topic,
        body=json.dumps({'findings': found, 'errors': errors, 'council': council_signals()}, ensure_ascii=False),
        sources=sources(found))
