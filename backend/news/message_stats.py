"""Jednakowe miary przekazu dla obu obozów. Bez wywołań modeli ani sieci."""
import re
import unicodedata

LINK = re.compile(r'(?:https?://|www\.)\S+', re.I)
# Liczba poza adresem, hashtagiem i identyfikatorem: kwoty, procenty, daty, liczebności.
NUMBER = re.compile(r'(?<![\w#@])\d+(?:[ .,/:\-]\d+)*(?:\s*(?:%|zł|pln|mln|mld|tys\.?))?(?!\w)', re.I)
REACTION = re.compile(r'^(?:(?:w punkt|dziękuj[ęe]|dziękujemy|dzięki|brawo|super|dokładnie|zgoda|tak|gratulacje)\s*)+$', re.I)
THANKS = re.compile(r'^(?:bardzo )?(?:dziękuję|dziękujemy|dzięki)(?: bardzo| serdecznie)?'
                    r'(?: wszystkim| wam| państwu)?(?: za (?:wsparcie|pomoc|życzenia|pamięć|obecność|dobre słowa|miłe słowa))?$', re.I)
TONES = ('atak', 'osiagniecie', 'apel', 'inne')


def concrete(text):
    return bool(LINK.search(text) or NUMBER.search(text))


def is_noise(text):
    text = unicodedata.normalize('NFC', text or '').strip()
    words = ' '.join(re.findall(r'[^\W\d_]+', text.lower()))
    return not concrete(text) and (len(text) < 40 or not words or bool(REACTION.fullmatch(words) or THANKS.fullmatch(words)))


def post_rows(posts):
    from news.clinic import figures_by_account
    figures = figures_by_account({p.account_id for p in posts})
    return [{'id': str(p.pk), 'author_id': str(figures[p.account_id].pk) if p.account_id in figures else f'account:{p.account_id}',
             'author': figures[p.account_id].canonical_name if p.account_id in figures else p.account.display_name,
             'text': p.text} for p in posts]


def calculate_stats(rows, points=None, tone=None):
    substantive = {str(p['id']): p for p in rows if not is_noise(p['text'])}
    author = lambda p: p.get('author_id', p['author'])
    authors = {author(p) for p in substantive.values()}
    count = len(substantive)
    concrete_count = sum(concrete(p['text']) for p in substantive.values())
    # Pierwszy wątek to główny wątek wskazany przez model. Nie zgadujemy dla starych przekazów.
    main = (points or [{}])[0].get('post_ids', [])
    main_authors = {author(substantive[str(pk)]) for pk in main if str(pk) in substantive}
    labels = {str(t.get('post_id')): t.get('label') for t in tone or []
              if str(t.get('post_id')) in substantive and t.get('label') in TONES}
    complete = bool(count) and len(labels) == count
    return {'version': 1, 'posts': count, 'authors': len(authors),
            'noise': sum(is_noise(p['text']) for p in rows),
            'concrete_count': concrete_count, 'concrete_pct': round(100 * concrete_count / count) if count else 0,
            'coherence_authors': len(main_authors) if main else None,
            'coherence_pct': round(100 * len(main_authors) / len(authors)) if main and authors else None,
            'tone': {label: round(100 * sum(v == label for v in labels.values()) / count, 1)
                     for label in TONES} if complete else None,
            'tone_classified': len(labels)}
