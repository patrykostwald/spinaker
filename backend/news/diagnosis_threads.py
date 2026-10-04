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


ENGLISH = re.compile(r'(the|and|of|is|are|was|were|in|for|to|with|that|has|have)', re.I)


def polish(text, fallback):
    """Zdanie po angielsku (zdarza się w polu claim) zastępujemy polskim wyjaśnieniem (konsylium 5.10)."""
    text = str(text or '').strip()
    if text and not re.search('[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', text) and len(ENGLISH.findall(text)) >= 2:
        return fallback or text
    return text or fallback


def boxes(diagnosis):
    """Łańcuch rozumowania Dr. Spina (właściciel 5.10: „ciąg logiczny, jasno czytelny”, bez powtórzeń):
    wniosek (diagnoza) - wynika z - wpis - tak przekonuje - chwyt - czy na pewno? - sprawdzone zdanie - bo - źródło.
    Połączenie mówi, dlaczego następny krok wynika z poprzedniego; nigdy nie powtarza tytułu boksu.
    Bez jednoliterowych słów w łącznikach (porównanie przy synchronizacji)."""
    from news.clinic import ASSESSMENT_LABELS, author_data
    from news.clinic_council import clean_claim

    post = diagnosis.post
    url = f'/klinika/{diagnosis.pk}'
    result = []

    def add(kind, title, href=url, *, body='', author='', date=None, note='', link_note='', link_kind='', image=''):
        data = {'kind': 'link', 'box_type': kind, 'title': short(title, 80),
                'url': href, 'domain': urlsplit(href).hostname or 'spin.clinic', 'title_origin': 'system',
                'body': short(body, 400), 'source_name': author, 'published_date': date}
        if image:
            data['image_url'] = image
        result.append({'box_data': data, 'note': short(note, 400), 'link_note': short(link_note) if result else '',
                       'link_kind': link_kind if result else ''})

    author = author_data(post, None)['name']
    # 1. wniosek: pełna diagnoza w naszej bazie, miniatura karty na zmianę z komentarzem Dr. Spina
    add('diagnosis', f'Spin {diagnosis.intensity or 0}/100: {diagnosis.headline}', body=sentence(diagnosis.summary) or sentence(diagnosis.headline),
        author='Dr. Spin', date=diagnosis.created_at.isoformat() if getattr(diagnosis, 'created_at', None) else None,
        note=sentence(diagnosis.summary) or sentence(diagnosis.headline), image=f'/api/clinic/spins/{diagnosis.pk}/card.png')
    # 2. z czego wynika: sam wpis
    add('post', post.text, post.url, body=post.text, author=author,
        date=post.published_at.isoformat() if post.published_at else None,
        link_note='Diagnoza dotyczy tego wpisu.', link_kind='wynika_z')
    # 3. jak przekonuje: chwyt (nazwa tylko w boksie)
    technique = next(iter(diagnosis.techniques or []), {})
    name = str(technique.get('name') or '').strip()
    name = name[:1].upper() + name[1:] if name else 'Bez wyraźnego chwytu'
    add('technique', name, body=sentence(technique.get('explanation')) or 'Dr. Spin nie wskazał tu żadnego chwytu.',
        link_note='Tak wpis próbuje przekonać czytelnika.', link_kind='jak')
    # 4-8. czy to prawda: sprawdzone zdania i ich źródła
    claims = [clean_claim(row) for row in (diagnosis.claims or []) if isinstance(row, dict)][:3]
    for index, claim in enumerate(claims):
        if len(result) >= 8:
            break
        label = ASSESSMENT_LABELS.get(claim.get('assessment'), 'niezweryfikowane')
        explanation = sentence(claim.get('explanation'))
        add('claim', f"{label[:1].upper() + label[1:]}: {polish(claim.get('claim'), explanation)}", body=explanation, link_kind='czy_na_pewno',
            link_note='Dr. Spin sprawdził jedno zdanie tego wpisu.' if index == 0 else 'Następne zdanie tego wpisu.')
        for source in claim.get('sources') or []:
            if len(result) >= 8:
                break
            if not isinstance(source, dict) or urlsplit(source.get('url') or '').scheme not in ('http', 'https'):
                continue
            add('source', source.get('title') or source['url'], source['url'], link_kind='bo',
                link_note='Ocena opiera się na tym źródle.')
    return result


OLD_DESCRIPTION = 'Spinka Dr. Spina (AI), ułożona automatycznie z opublikowanej diagnozy.'


def description(diagnosis):
    """Podtytuł (właściciel 5.10): czyj wpis analizował Dr. Spin i jakich technik użyto; Redaktor tytułów odmienia nazwisko."""
    from news.clinic import author_data
    names = [str(t.get('name') or '').strip().lower() for t in (diagnosis.techniques or []) if isinstance(t, dict)]
    names = [n for n in names if n][:4]
    text = f"Analiza wpisu: {author_data(diagnosis.post, None)['name']}."
    if names:
        text += ' Techniki: ' + ', '.join(names) + '.'
    return short(text, 170)


@transaction.atomic
def min_intensity():
    import os
    try:
        return int(os.environ.get('DRSPIN_THREAD_MIN_INTENSITY', '70'))
    except ValueError:
        return 70


@draft_builder
def sync_diagnosis_thread(diagnosis_id, force_text=False):
    """Blokada diagnozy i OneToOne chronią przed podwójną publikacją. Nie cofamy moderacji."""
    diagnosis = SpinDiagnosis.objects.select_for_update(of=('self',)).select_related('post__account').get(pk=diagnosis_id)
    visible = (diagnosis.status == 'approved' and not diagnosis.withdrawn_at
               and not diagnosis.hidden_at and diagnosis.post.available)
    if not visible:
        PersonalContextThread.objects.filter(diagnosis=diagnosis).update(is_public=False)
        return None
    # Spinki tylko z mocnych diagnoz (właściciel 5.10: od 70/100); słabsze nie powstają, a dawne są ukryte.
    if (diagnosis.intensity or 0) < min_intensity():
        PersonalContextThread.objects.filter(diagnosis=diagnosis).update(is_public=False)
        return None
    thread, _ = PersonalContextThread.objects.get_or_create(diagnosis=diagnosis, defaults={
        'title': short('Diagnoza: ' + diagnosis.headline, 65), 'description': description(diagnosis),
        'is_public': False, 'published_at': diagnosis.reviewed_at or diagnosis.diagnosed_at or diagnosis.created_at})
    title, about = short('Diagnoza: ' + diagnosis.headline, 65), description(diagnosis)
    payload = boxes(diagnosis)
    existing = list(thread.items.values('box_data', 'note', 'link_note', 'link_kind'))
    if existing != payload:
        thread.items.all().delete()
        PersonalContextThreadItem.objects.bulk_create([
            PersonalContextThreadItem(thread=thread, position=index, **row) for index, row in enumerate(payload)])
    # podtytuł potem pisze Redaktor tytułów; zastępujemy tylko dawny, niezrozumiały szablon
    if force_text or thread.description == OLD_DESCRIPTION or thread.description.startswith(('Dr. Spin (AI) sprawdził wpis:', 'Dr. Spin (AI) wyjaśnia, jaki spin')):
        thread.description = about
        thread.save(update_fields=['description'])
    if existing != payload or thread.title != title or not thread.is_public:
        thread.title, thread.is_public = title, False
        thread.save(update_fields=['title', 'is_public', 'updated_at'])
    from news.thread_review import enqueue
    enqueue(thread, {'post': diagnosis.post.text, 'author': diagnosis.post.account.display_name,
        'diagnosis': {key: getattr(diagnosis, key) for key in ('headline', 'summary', 'analysis', 'claims', 'techniques')}})
    return thread
