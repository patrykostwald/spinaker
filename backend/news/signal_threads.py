"""Deterministic signals over local records. Never fetches sources or calls AI."""
import re
from collections import defaultdict
from datetime import timedelta
from difflib import SequenceMatcher
from itertools import combinations
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.diagnosis_threads import short
from news.message_structure import phrase_ngrams
from news.thread_review import digest, enqueue, draft_builder

WARSAW = ZoneInfo('Europe/Warsaw')
NEW_METHOD = ('Metoda: co najmniej 3 autorów w 48 godzin, bez tej frazy w poprzednich 14 dniach '
              'zebranej bazy; porównanie dosłownych fraz tą samą miarą dla obu stron.')


def box(kind, title, url, body='', source='', connection='', **extra):
    return {'box_data': {'kind': 'link', 'box_type': kind, 'title': short(title, 80), 'url': url,
        'domain': urlsplit(url).hostname or 'spin.clinic', 'title_origin': 'system',
        'body': short(body, 400), 'source_name': source, **extra}, 'note': '', 'link_note': short(connection, 200)}


def find_new_phrases(rows, now):
    """Baseline is [now-16d, now-48h); current window is [now-48h, now]."""
    start = now - timedelta(hours=48)
    baseline = set()
    groups = defaultdict(list)
    for row in sorted(rows, key=lambda r: (r['published_at'], str(r['id']))):
        if not now - timedelta(days=16) <= row['published_at'] <= now:
            continue
        phrases = phrase_ngrams(row['text'])
        if row['published_at'] < start:
            baseline.update(phrases)
        else:
            for phrase in phrases:
                groups[phrase].append(row)
    found = []
    for phrase, posts in groups.items():
        authors = {p['author_id'] for p in posts}
        parties = {p.get('party') for p in posts if p.get('party')}
        camps = {p['camp'] for p in posts}
        accounts = {p['account_id'] for p in posts}
        if phrase in baseline or len(authors) < 3 or not (len(parties) >= 2 or
            (len(camps) == 1 and len(accounts) >= 3) or camps >= {'government', 'opposition'}):
            continue
        found.append({'phrase': phrase, 'posts': posts, 'authors': len(authors),
            'reach': sum(max(0, p.get('reach', 0)) for p in posts)})
    found.sort(key=lambda r: (-r['authors'], -r['reach'], -len(r['phrase'].split()), r['phrase']))
    # One story for overlapping phrases carried by the same group of posts.
    selected = []
    for row in found:
        ids = {p['id'] for p in row['posts']}
        if any(len(ids & {p['id'] for p in old['posts']}) / len(ids | {p['id'] for p in old['posts']}) >= .6
               for old in selected):
            continue
        selected.append(row)
    return selected


def narrative_boxes(candidate):
    posts = candidate['posts']
    selected, authors = [], set()
    # Always retain the earliest occurrence, then ensure both camps fit in the strip.
    for post in posts:
        if post['author_id'] not in authors:
            selected.append(post)
            authors.add(post['author_id'])
    chosen = selected[:6]
    for camp in ('government', 'opposition'):
        if any(p['camp'] == camp for p in selected) and not any(p['camp'] == camp for p in chosen):
            chosen[-1] = next(p for p in selected if p['camp'] == camp)
    chosen.sort(key=lambda p: (p['published_at'], str(p['id'])))
    strongest = max((p for p in posts if p.get('diagnosis')), key=lambda p: (p['diagnosis']['intensity'], str(p['id'])), default=None)
    result = [box('post', p['text'], p['url'], p['text'], p['author'],
        connection=('To samo sformułowanie: ' + candidate['phrase']) if i else '',
        political_post_id=p['id'], published_date=p['published_at'].isoformat()) for i, p in enumerate(chosen)]
    techniques = []
    if strongest:
        d = strongest['diagnosis']
        result.append(box('diagnosis', d['headline'], f"/klinika/{d['id']}",
            connection='Diagnoza najsilniejszego ocenionego wpisu z tą frazą.', diagnosis_id=d['id']))
        techniques = [t.get('name', '') for t in d['techniques'] if isinstance(t, dict)][:2]
    origin = chosen[0]['author']
    body = (f'Najwcześniejszy wpis z tą frazą w badanym oknie: {origin}. '
            f'Fraza pojawia się u {candidate["authors"]} autorów. '
            'Kolejność wpisów pokazuje jej obecność w czasie, bez wskazywania przyczyny.')
    if techniques:
        body += ' Techniki w dołączonej diagnozie: ' + ', '.join(techniques) + '.'
    else:
        body += ' Brak diagnozy technik w tym zestawie.'
    result.append(box('summary', 'Nowa narracja - podsumowanie', '#podsumowanie', body,
                      connection='Zbieżność frazy w pokazanych wpisach.'))
    return result


@transaction.atomic
@draft_builder
def save_signal(kind, key, title, description, items, evidence, metadata):
    signature = digest([title, description, items, evidence])
    metadata = {**metadata, 'source_signature': signature}
    thread, created = PersonalContextThread.objects.get_or_create(signal_key=key, defaults={
        'signal_kind': kind, 'title': title, 'description': description, 'signal_data': metadata})
    if not created and thread.signal_data.get('source_signature') == signature:
        return thread
    if not created:
        thread.title, thread.description, thread.signal_data, thread.is_public = title, description, metadata, False
        thread.save()
        thread.items.all().delete()
    PersonalContextThreadItem.objects.bulk_create([
        PersonalContextThreadItem(thread=thread, position=i, **item) for i, item in enumerate(items)])
    enqueue(thread, evidence)
    return thread


@transaction.atomic
def build_new_narratives(now=None):
    from news.features import threads_enabled
    from news.models import RepairerState
    from news.political_models import PoliticalPost
    from news.message_stats import post_rows
    from news.clinic import published_diagnoses
    if not threads_enabled():
        return []
    now = now or timezone.now()
    day = now.astimezone(WARSAW).date()
    state, _ = RepairerState.objects.get_or_create(key='new-narrative-quota:' + day.isoformat())
    RepairerState.objects.select_for_update().get(pk=state.pk)
    used = PersonalContextThread.objects.filter(signal_kind='new_narrative', signal_data__day=day.isoformat()).count()
    if used >= 2:
        return []
    posts = list(PoliticalPost.objects.filter(available=True, published_at__gte=now-timedelta(days=16),
        published_at__lte=now).select_related('account'))
    authors = {r['id']: r for r in post_rows(posts)}
    diagnoses = {d.post_id: d for d in published_diagnoses().filter(post__in=posts)}
    rows = []
    for p in posts:
        metrics = p.source_data.get('public_metrics', {})
        reach = metrics.get('impression_count', 0)
        row = {**authors[str(p.pk)], 'id': p.pk, 'url': p.url, 'account_id': p.account_id,
            'camp': p.camp_at_collection, 'published_at': p.published_at,
            'reach': reach if type(reach) is int else 0}
        if p.pk in diagnoses:
            d = diagnoses[p.pk]
            row['diagnosis'] = {'id': d.pk, 'headline': d.headline, 'intensity': d.intensity, 'techniques': d.techniques}
        rows.append(row)
    result = []
    for candidate in find_new_phrases(rows, now):
        ids = {p['id'] for p in candidate['posts']}
        prior = PersonalContextThread.objects.filter(signal_kind='new_narrative', created_at__gte=now-timedelta(days=16))
        if any(ids & set(t.signal_data.get('post_ids', [])) for t in prior):
            continue
        evidence = {**candidate, 'posts': [{**p, 'published_at': p['published_at'].isoformat()} for p in candidate['posts']], 'method': NEW_METHOD}
        thread = save_signal('new_narrative', digest(['new_narrative', candidate['phrase'], min(ids)]),
            short('Nowa narracja: ' + candidate['phrase'], 65),
            short(f"Fraza pojawiła się u {candidate['authors']} autorów. Pokazujemy, kto użył jej pierwszy, oraz kolejne wpisy.", 170),
            narrative_boxes(candidate), evidence,
            {'day': day.isoformat(), 'phrase': candidate['phrase'], 'post_ids': sorted(ids), 'authors': candidate['authors'], 'reach': candidate['reach']})
        result.append(thread.pk)
        if used + len(result) == 2:
            break
    return result


def normalized(text):
    return ' '.join(re.findall(r'\w+', str(text).casefold()))


def similarity(a, b):
    a, b = normalized(a), normalized(b)
    if min(len(a), len(b)) <= 120 or abs(len(a)-len(b)) > .4 * max(len(a), len(b)):
        return 0
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    return matcher.ratio() if matcher.quick_ratio() >= .8 else 0


def confidence(kind, score=0, technical=False):
    if kind in ('registry', 'declaration'):
        return 'wysoki'
    if technical or score < .72:
        return 'niski'
    return 'wysoki' if score >= .95 else 'średni'


def lobbying_signals(records):
    """Input contract: print, term, kind, text, url, author, clubs, id.

    Registration requires an explicit print binding; general membership is not a signal.
    """
    valid = [r for r in records if r.get('print') and r.get('term') and r.get('text') and
             urlsplit(r.get('url', '')).scheme in ('http', 'https')]
    results = []
    for row in valid:
        if row['kind'] in ('registry', 'declaration') and row.get('confirmed') is True and row.get('author'):
            results.append({'kind': row['kind'], 'a': row, 'b': None, 'score': 1,
                'confidence': confidence(row['kind']), 'connection': 'Zgłoszone przez: ' + row['author']})
    for a, b in combinations(valid, 2):
        if (a['term'], a['print']) != (b['term'], b['print']):
            continue
        if a['kind'] != 'amendment':
            a, b = b, a
        if a['kind'] != 'amendment':
            continue
        kind = 'twins' if b['kind'] == 'amendment' else 'consultation'
        if kind == 'twins':
            if not a.get('clubs') or not b.get('clubs') or set(a['clubs']) & set(b['clubs']):
                continue
        elif b['kind'] not in ('consultation', 'position') or not b.get('author'):
            continue
        score = similarity(a['text'], b['text'])
        technical = bool(re.search(r'wchodzi w życie|wejścia w życie|skreśla się wyraz', a['text'], re.I))
        level = confidence(kind, score, technical)
        if score < .72:
            continue
        connection = ('Ten sam zapis' if normalized(a['text']) == normalized(b['text']) else 'Zbieżne sformułowanie')
        if kind == 'consultation':
            connection += '; zgłoszone w konsultacjach przez: ' + b['author']
        results.append({'kind': kind, 'a': a, 'b': b, 'score': round(score, 4),
                        'confidence': level, 'connection': connection + '.'})
    return results


def build_lobbying(records=None):
    from news.features import threads_enabled
    if not threads_enabled():
        return []
    records = local_lobbying_records() if records is None else records
    results = []
    for signal in lobbying_signals(records):
        if signal['confidence'] == 'niski':
            continue
        a, b = signal['a'], signal['b']
        key = digest(['lobbying', signal['kind'], sorted([str(a['id']), str(b['id']) if b else ''])])
        number, term = a['print'], a['term']
        url = f'https://api.sejm.gov.pl/sejm/term{term}/prints/{number}'
        items = [box('print', f'Druk {number}', url, a.get('project_title', '')),
                 box(a['kind'], a.get('label', 'Fragment dokumentu'), a['url'], a['text'], a.get('author', ''),
                     connection='Fragment dotyczący tego projektu.')]
        if b:
            items.append(box(b['kind'], b.get('label', 'Zbieżny fragment'), b['url'], b['text'], b.get('author', ''),
                             connection=signal['connection']))
        # Exact print references only; no loose topic/name matching.
        from news.political_models import PoliticalPost
        pattern = re.compile(r'\bdruk(?:u|iem|owi)?\s*(?:nr\.?\s*)?' + re.escape(number) + r'(?![\w-])', re.I)
        posts = [p for p in PoliticalPost.objects.filter(available=True, text__icontains=number).select_related('account')
                 if pattern.search(p.text) and p.source_data.get('sejm_term') == term][:3]
        for p in posts:
            items.append(box('post', p.text, p.url, p.text, p.account.display_name,
                connection='Wpis wymienia ten druk.', political_post_id=p.pk, published_date=p.published_at.isoformat()))
        body = ('Zbieżność dotyczy pokazanych fragmentów. Sam wspólny zapis nie wskazuje, kto go przygotował '
                'ani dlaczego został zgłoszony.') if b else 'Zapis dokumentuje zgłoszenie dotyczące tego projektu. Sam wpis nie wskazuje wpływu na treść ustawy.'
        items.append(box('summary', 'Sygnał lobbingu - podsumowanie', '#podsumowanie', body, connection=signal['connection']))
        rule = ('jawne zgłoszenie powiązane z drukiem' if not b else
                f'podobieństwo tekstów {signal["score"]:.0%}, próg średni 72%, wysoki 95%, bez przepisów szablonowych')
        method = f'Metoda: {rule}, ta sama miara dla wszystkich klubów; poziom pewności sygnału: {signal["confidence"]}.'
        evidence = {'signal': signal, 'posts': [{'text': p.text, 'author': p.account.display_name, 'camp_at_collection': p.camp_at_collection} for p in posts], 'method': method}
        about = (f'Analiza druku {number}: zgłoszone zapisy zestawione ze stanowiskami organizacji. '
                 'Zbieżność tekstu nie wskazuje autora ani przyczyny.')
        results.append(save_signal('lobbying', key, f'Sygnał lobbingu: druk {number}', about, items, evidence,
                                   {'confidence': signal['confidence'], 'rule': rule, 'print': number}).pk)
    return results


def local_lobbying_records():
    """090 adapter. Unbound registry entries are deliberately excluded.

    OfficialRecord.raw_data.amendments is the import hook for structured amendments;
    stored full text can be parsed without any HTTP/PDF request.
    """
    from news.models import OfficialRecord
    from news.public_records_models import PublicRecord
    from news.lobbying_rules import amendments, declarations
    result = []
    for record in OfficialRecord.objects.filter(provider='sejm', external_id__startswith='print/').select_related('article'):
        _, term, number = record.external_id.split('/', 2)
        content = getattr(record.article, 'content', None)
        text = content.text if content else record.raw_data.get('text', '')
        parsed = record.raw_data.get('amendments') or amendments(text)
        for row in parsed:
            if not isinstance(row, dict):
                continue
            result.append({'id': f'official:{record.pk}:{row.get("number")}', 'term': int(term),
                'print': number.split('-')[0], 'kind': 'amendment', 'text': row.get('text', ''),
                'url': row.get('source_url') or record.article.url, 'author': ', '.join(row.get('clubs', [])),
                'clubs': row.get('clubs', []), 'label': f'Poprawka {row.get("number", "")}', 'project_title': record.article.title})
        for i, row in enumerate(declarations(text)):
            result.append({'id': f'declaration:{record.pk}:{i}', 'term': int(term), 'print': number.split('-')[0],
                'kind': 'declaration', 'url': content.source_url if content else record.article.url,
                'confirmed': True, 'label': 'Zgłoszenie w uzasadnieniu', **row})
    for row in PublicRecord.objects.filter(kind__in=['consultation', 'lobby_activity', 'lobby_declaration', 'amendment', 'position']).exclude(print_number=''):
        if not row.term:
            continue
        kind = {'lobby_activity': 'registry', 'lobby_declaration': 'declaration'}.get(row.kind, row.kind)
        result.append({'id': f'public:{row.pk}', 'term': row.term, 'print': row.print_number.split('-')[0],
            'kind': kind, 'url': row.source_url, 'text': row.text or row.data.get('cytat_uwagi', ''),
            'author': row.title, 'clubs': row.data.get('clubs', []), 'confirmed': row.data.get('confirmed') is True,
            'label': row.title})
    return result
