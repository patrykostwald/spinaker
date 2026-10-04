"""Narratives from validated daily-message assignments. No AI or network calls."""
import re
from django.db import transaction
from django.utils import timezone
from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.clinic_models import ClinicDailyMessage
from news.diagnosis_threads import short
from news.message_stats import TONES, NUMBER, post_rows
from news.thread_review import draft_builder

CRITERION = 'Dla obu stron: co najmniej 3 wpisy od 2 autorów w jednym wątku z przypisanym tonem lub techniką.'


def candidates(message):
    from news.clinic import published_diagnoses
    posts = list(message.posts.filter(available=True, camp_at_collection=message.camp,
        published_at__date=message.day).select_related('account'))
    authors = {row['id']: row['author_id'] for row in post_rows(posts)}
    tones = {str(row.get('post_id')): row['label'] for row in message.tone
             if isinstance(row, dict) and row.get('label') in TONES}
    diagnoses = {row.post_id: row for row in published_diagnoses().filter(post__in=posts)}
    result = []
    for point in message.points:
        if not isinstance(point, dict) or not point.get('title'):
            continue
        ids = set(str(pk) for pk in point.get('post_ids', []))
        rows = [p for p in posts if str(p.pk) in ids]
        distinct = {authors[str(p.pk)] for p in rows}
        classified = any(str(p.pk) in tones or (p.pk in diagnoses and diagnoses[p.pk].techniques) for p in rows)
        if len(rows) < 3 or len(distinct) < 2 or not classified:
            continue
        # Same ranking for both camps: coverage, then diagnosis intensity, then stable ID.
        strongest = max((diagnoses[p.pk] for p in rows if p.pk in diagnoses and diagnoses[p.pk].verdict == 'spin'),
            key=lambda d: (d.intensity, d.pk), default=None)
        result.append({'point': point, 'posts': rows, 'authors': authors, 'tones': tones, 'diagnosis': strongest,
            'score': len(rows) * 1000 + len(distinct) * 100 + (strongest.intensity if strongest else 0)})
    return sorted(result, key=lambda row: row['score'], reverse=True)


def payload(message, candidate):
    from news.dr_spin_threads import STOP_WORDS
    point, tones = candidate['point'], candidate['tones']
    words = lambda text: {w for w in re.findall(r'\w+', text.lower()) if len(w) >= 4 and w not in STOP_WORDS}
    rows = sorted(candidate['posts'], key=lambda p: (-len(words(p.text) & words(point['title'] + ' ' + point.get('summary', ''))), p.pk))
    selected, seen = [], set()
    for post in rows:
        author = candidate['authors'][str(post.pk)]
        if author not in seen:
            selected.append(post)
            seen.add(author)
        if len(selected) == 4:
            break
    result = []
    def add(kind, title, url, body='', source='', date=None, connection=''):
        result.append({'box_data': {'kind': 'link', 'box_type': kind, 'title': short(title, 80), 'url': url,
            'domain': 'x.com' if kind == 'post' else 'spin.clinic', 'title_origin': 'system',
            'body': short(body, 400), 'source_name': source, 'published_date': date}, 'note': '',
            'link_note': short(connection, 200) if result else ''})
    previous = None
    for post in selected:
        connection = 'Wspólny wątek: ' + point['title']
        if previous:
            shared = sorted(words(previous.text) & words(post.text))[:3]
            numbers = sorted(set(NUMBER.findall(previous.text)) & set(NUMBER.findall(post.text)))[:3]
            if numbers:
                connection = 'Powtórzone liczby: ' + ', '.join(numbers) + '.'
            elif shared:
                connection = 'Powtórzone słowa: ' + ', '.join(shared) + '.'
            elif tones.get(str(post.pk)) and tones.get(str(post.pk)) == tones.get(str(previous.pk)):
                connection += '. Wspólny ton: ' + tones[str(post.pk)] + '.'
        add('post', post.text, post.url, post.text, post.account.display_name,
            post.published_at.isoformat(), connection)
        result[-1]['box_data'].update({'political_post_id': post.pk, 'x_handle': post.account.handle.lstrip('@')})
        previous = post
    diagnosis = candidate['diagnosis']
    if diagnosis:
        add('diagnosis', diagnosis.headline, f'/klinika/{diagnosis.pk}',
            connection=f'Diagnoza wpisu z tego wątku: siła spinu {diagnosis.intensity}/100.')
        result[-1]['box_data']['diagnosis_id'] = diagnosis.pk
    add('message', 'Przekaz dnia: ' + message.day.isoformat(),
        f'/klinika/przekazy/{message.day}#message-{message.day}-{message.camp}',
        message.thesis or message.message, connection='Ten wątek jest częścią przekazu dnia tej strony.')
    return result


@transaction.atomic
@draft_builder
def sync_message(message_id):
    message = ClinicDailyMessage.objects.select_for_update().get(pk=message_id)
    eligible = candidates(message) if message.status == 'approved' else []
    if not eligible:
        PersonalContextThread.objects.filter(narrative_message=message).update(is_public=False)
        return None
    best = eligible[0]
    thread, _ = PersonalContextThread.objects.get_or_create(narrative_message=message, defaults={
        'title': short('Przekaz dnia: ' + best['point']['title'], 65), 'published_at': timezone.now()})
    data = payload(message, best)
    if list(thread.items.values('box_data', 'note', 'link_note')) != data:
        thread.items.all().delete()
        PersonalContextThreadItem.objects.bulk_create([PersonalContextThreadItem(thread=thread, position=i, **row) for i, row in enumerate(data)])
    thread.title = short('Przekaz dnia: ' + best['point']['title'], 65)
    # jeden szablon spinek Dr. Spina (właściciel 5.10): co zbadano, co pokazujemy; metoda zostaje w dowodach recenzji
    authors = len({p.account_id for p in best['posts']})
    side = 'rządzących' if message.camp == 'government' else 'opozycji'
    thread.description = short(f"Analiza {len(best['posts'])} wpisów od {authors} autorów ({side}), dzień {message.day.strftime('%d.%m.%Y')}. "
                               'Pokazujemy, jak powtarzają ten sam wątek.', 170)
    thread.is_public, thread.narrative_score = False, best['score']
    thread.save(update_fields=['title', 'description', 'is_public', 'narrative_score', 'updated_at'])
    from news.thread_review import enqueue
    enqueue(thread, {'posts': [{'text': p.text, 'author': p.account.display_name} for p in best['posts']],
        'thesis': message.thesis, 'points': message.points, 'tone': message.tone, 'method': CRITERION})
    return thread


def build_narratives(day=None):
    from news.features import threads_enabled
    if not threads_enabled():
        return {'status': 'disabled'}
    day = day or timezone.localdate()
    results = {}
    for message in ClinicDailyMessage.objects.filter(day=day, camp__in=['government', 'opposition']):
        thread = sync_message(message.pk)
        results[message.camp] = thread.pk if thread else None
    return {'status': 'created' if any(results.values()) else 'not_applicable', 'threads': results}
