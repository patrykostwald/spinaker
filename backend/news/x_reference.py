import re
from urllib.parse import urlsplit
from rest_framework.exceptions import ValidationError

def normalize_x_url(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValidationError('Nieprawidłowy adres posta.')
    if parsed.scheme != 'https' or parsed.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'} or parsed.username or port:
        raise ValidationError('Podaj bezpośredni adres HTTPS posta na X.')
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/([0-9]+)(?:/)?', parsed.path)
    if not match:
        raise ValidationError('Adres powinien zawierać nazwę konta i /status/numer.')
    return f'https://x.com/{match[1]}/status/{match[2]}'

def reference_card(url, key=0):
    # A presentation-only link, never an Article database record or inferred post text.
    return {'id': -key, 'reference_only': True, 'title': 'Post na X — odnośnik', 'url': url,
        'published_date': None, 'date_precision': 'time', 'category': 'tweet', 'image_url': '',
        'source': {'id': 0, 'name': 'X', 'url': 'https://x.com', 'source_type': 'twitter'},
        'author': '', 'description': '', 'discovered_at': None, 'ingestion_method': 'reference',
        'category_reviewed': False, 'evidence_note': 'Treści i dostępności posta nie zweryfikowano. Link dodany przez autora nitki.'}
