"""Rozkład każdej opublikowanej diagnozy. Wyłącznie zapisane dane, bez wywołań AI/HTTP."""
import re
from urllib.parse import urlsplit

from django.db import transaction

from news.account_models import PersonalContextThread, PersonalContextThreadItem
from news.clinic_models import SpinDiagnosis
from news.thread_review import draft_builder


def short(value, limit=200):
    value = ' '.join(str(value or '').replace('—', '-').replace('–', '-').split())
    if len(value) <= limit:
        return value
    candidate = value[:limit - 1]
    ends = list(re.finditer(r'[.!?](?=\s|$)', candidate))
    if ends:
        return candidate[:ends[-1].end()]
    return candidate.rsplit(' ', 1)[0] + '…'


def sentence(value):
    return short(re.split(r'(?<=[.!?])\s+', str(value or ''), maxsplit=1)[0])


def boxes(diagnosis):
    from news.clinic import ASSESSMENT_LABELS, author_data
    from news.clinic_council import clean_claim

    post = diagnosis.post
    url = f'/klinika/{diagnosis.pk}'
    result = []

    def add(kind, title, href=url, *, body='', author='', date=None, note='', link_note=''):
        result.append({'box_data': {'kind': 'link', 'box_type': kind, 'title': short(title, 80),
            'url': href, 'domain': urlsplit(href).hostname or 'spin.clinic', 'title_origin': 'system',
            'body': short(body, 400), 'source_name': author, 'published_date': date},
            'note': short(note, 400), 'link_note': short(link_note) if result else ''})

    author = author_data(post, None)['name']
    add('post', post.text, post.url, body=post.text, author=author,
        date=post.published_at.isoformat() if post.published_at else None)
    technique = next(iter(diagnosis.techniques or []), {})
    technique_note = short(f"Technika: {technique.get('name') or 'brak wskazanej techniki'}. "
                           f"{sentence(technique.get('explanation'))}")
    add('technique', 'Technika: ' + (technique.get('name') or 'Brak wskazanej techniki'),
        body=sentence(technique.get('explanation')) or 'W diagnozie nie wskazano techniki perswazji.', link_note=technique_note)
    claims = [clean_claim(row) for row in (diagnosis.claims or []) if isinstance(row, dict)][:3]
    for index, claim in enumerate(claims):
        if len(result) >= 7:
            break
        assessment = ASSESSMENT_LABELS.get(claim.get('assessment'), 'niezweryfikowane')
        add('claim', f"{assessment}: {claim.get('claim', '')}", body=sentence(claim.get('explanation')),
            link_note=technique_note if index == 0 else 'Kolejne sprawdzone twierdzenie')
        for source in claim.get('sources') or []:
            if len(result) >= 7:
                break
            if not isinstance(source, dict) or urlsplit(source.get('url') or '').scheme not in ('http', 'https'):
                continue
            add('source', source.get('title') or source['url'], source['url'],
                link_note=sentence(claim.get('explanation')) or 'Źródło przywołane przy tym twierdzeniu.')
    add('diagnosis', 'Pełna diagnoza: ' + diagnosis.headline,
        link_note=sentence(diagnosis.headline))
    return result


@transaction.atomic
@draft_builder
def sync_diagnosis_thread(diagnosis_id):
    """Blokada diagnozy i OneToOne chronią przed podwójną publikacją. Nie cofamy moderacji."""
    diagnosis = SpinDiagnosis.objects.select_for_update().select_related('post__account').get(pk=diagnosis_id)
    visible = (diagnosis.status == 'approved' and not diagnosis.withdrawn_at
               and not diagnosis.hidden_at and diagnosis.post.available)
    if not visible:
        PersonalContextThread.objects.filter(diagnosis=diagnosis).update(is_public=False)
        return None
    thread, _ = PersonalContextThread.objects.get_or_create(diagnosis=diagnosis, defaults={
        'title': short('Rozkład: ' + diagnosis.headline, 80),
        'description': 'Nitka Dr. Spina (AI), ułożona automatycznie z opublikowanej diagnozy.',
        'is_public': False, 'published_at': diagnosis.reviewed_at or diagnosis.diagnosed_at or diagnosis.created_at})
    title = short('Rozkład: ' + diagnosis.headline, 80)
    payload = boxes(diagnosis)
    existing = list(thread.items.values('box_data', 'note', 'link_note'))
    if existing != payload:
        thread.items.all().delete()
        PersonalContextThreadItem.objects.bulk_create([
            PersonalContextThreadItem(thread=thread, position=index, **row) for index, row in enumerate(payload)])
    if existing != payload or thread.title != title or not thread.is_public:
        thread.title, thread.is_public = title, False
        thread.save(update_fields=['title', 'is_public', 'updated_at'])
    from news.thread_review import enqueue
    enqueue(thread, {'post': diagnosis.post.text, 'author': diagnosis.post.account.display_name,
        'diagnosis': {key: getattr(diagnosis, key) for key in ('headline', 'summary', 'analysis', 'claims', 'techniques')}})
    return thread
