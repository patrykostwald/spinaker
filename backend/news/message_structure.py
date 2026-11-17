"""Walidacja przypisań AI do rzeczywistego wejścia przekazu."""
import re

from news.message_stats import TONES


def phrase_ngrams(text):
    """Literal 3-6 word phrases, sentence bounded; links/handles are not theses."""
    from news.dr_spin_threads import STOP_WORDS
    from news.message_stats import LINK
    text = re.sub(r'@\w+', ' ', LINK.sub(' ', text or '')).casefold()
    phrases = set()
    for sentence in re.split(r'[.!?;\n]', text):
        words = re.findall(r'[^\W_]+', sentence)
        for size in range(3, 7):
            for start in range(len(words) - size + 1):
                part = words[start:start + size]
                if sum(len(w) >= 4 and w not in STOP_WORDS for w in part) >= 2:
                    phrases.add(' '.join(part))
    return phrases


def clean_structure(data, rows, camp):
    from news.clinic_ai import ClinicAIError, looks_polish
    empty = {'thesis': '', 'points': [], 'tone': []}
    def reject():
        raise ClinicAIError('invalid_message_structure')

    if not isinstance(data, dict):
        reject()
    if not any(data.get(key) for key in empty):
        return empty  # starszy model: zachowujemy message i analysis

    def one_sentence(text):
        # Skróty i daty nie rozdzielają zdań. Odrzucamy kolejne zdanie po interpunkcji.
        return not re.search(r'[!?]|\.\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])', text)

    if data.get('camp') != camp:
        reject()
    thesis = data.get('thesis')
    points, tone = data.get('points'), data.get('tone')
    if (not isinstance(thesis, str) or not 1 <= len(thesis) <= 160
            or re.search(r'[—–\n]', thesis) or not one_sentence(thesis)):
        reject()
    # Obóz pochodzi z redakcyjnej klasyfikacji wejścia. Model nie nadaje mu nazwy partii.
    subject = 'Rządzący' if camp == 'government' else 'Opozycja'
    verbs = r'(?:podkreślają|podkreśla|mówią|mówi|akcentują|akcentuje|wskazują|wskazuje|apelują|apeluje|przedstawiają|przedstawia|zapowiadają|zapowiada|krytykują|krytykuje|opisują|opisuje|skupiają|skupia)'
    if not re.match(rf'^{subject} {verbs}\b', thesis):
        reject()
    if not isinstance(points, list) or not 2 <= len(points) <= 3 or not isinstance(tone, list):
        reject()
    posts = {str(p['id']): p for p in rows}
    cleaned = []
    for point in points:
        if not isinstance(point, dict):
            reject()
        title, summary = point.get('title'), point.get('summary')
        ids, names = point.get('post_ids'), point.get('authors')
        if (not isinstance(title, str) or not 1 <= len(title) <= 70 or not isinstance(summary, str)
                or not summary.strip() or not one_sentence(summary) or re.search(r'[—–\n]', title + summary)
                or not isinstance(ids, list) or not ids or not isinstance(names, list) or not names):
            reject()
        if any(not isinstance(pk, str) or pk not in posts for pk in ids) or len(set(ids)) != len(ids):
            reject()
        actual_names = {posts[pk]['author'] for pk in ids}
        # Nazwisko lub pełna nazwa muszą pochodzić z autorów tych konkretnych wpisów.
        allowed = actual_names | {name.split()[-1] for name in actual_names if name.split()}
        if any(not isinstance(name, str) or name not in allowed for name in names):
            reject()
        cleaned.append({'title': title, 'summary': summary, 'post_ids': ids, 'authors': sorted(actual_names)})
    labels = {}
    for item in tone:
        if (not isinstance(item, dict) or not isinstance(item.get('post_id'), str)
                or item['post_id'] not in posts or item['post_id'] in labels or item.get('label') not in TONES):
            reject()
        labels[item['post_id']] = item['label']
    if set(labels) != set(posts):
        reject()
    if not looks_polish(' '.join([thesis, *(p['summary'] for p in cleaned)])):
        reject()
    return {'thesis': thesis, 'points': cleaned, 'tone': [{'post_id': pk, 'label': label} for pk, label in labels.items()]}
