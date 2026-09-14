import json
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urlsplit
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import serializers
from news.models import Article
from news.classification import publisher_category, normalize_publisher_tags, declared_category
from news.serializers import ArticleSerializer
from scraper.utils import fetch_feed, parse_published, safe_url
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self.in_title = {}, '', False
        self.canonical = ''
        self.in_json = False
        self.json_buffer = ''
        self.json_documents = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.in_json = True; self.json_buffer = ''
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            if key and attrs.get('content'):
                self.meta.setdefault(key, attrs['content'].strip())
        if tag == 'link' and 'canonical' in (attrs.get('rel') or '').lower().split():
            self.canonical = attrs.get('href', '').strip()

    def handle_endtag(self, tag):
        if tag == 'script' and self.in_json:
            try: self.json_documents.append(json.loads(self.json_buffer))
            except (ValueError, RecursionError): pass
            self.in_json = False
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_json: self.json_buffer += data
        if self.in_title:
            self.title += data


def decode_source_html(raw):
    # HTML charset is explicit where available; use HTML5-compatible UTF-8 otherwise.
    import re
    charset = re.search(br'charset\s*=\s*["\x27]?([\w-]+)', raw[:8192], re.I)
    encoding = charset.group(1).decode('ascii') if charset else 'utf-8'
    try:
        html = raw.decode(encoding, errors='replace')
    except LookupError:
        html = raw.decode('utf-8', errors='replace')
    return html


def article_identity(node, requested_url):
    """Classify all declared article addresses, keeping meaningful query strings."""
    addresses = []
    for key in ('url', 'mainEntityOfPage'):
        address = node.get(key)
        if address is None or address == '':
            continue
        if isinstance(address, dict):
            address = address.get('@id')
        if not isinstance(address, str) or not address.strip():
            return 'foreign'
        addresses.append(address.strip())
    if not addresses:
        return 'anonymous'

    def page_key(address):
        parsed = urlsplit(urljoin(requested_url, address))
        return (parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/'), parsed.query)

    try:
        requested = page_key(requested_url)
        return 'matched' if all(page_key(address) == requested for address in addresses) else 'foreign'
    except ValueError:
        return 'foreign'


def extract_metadata(raw, url):
    parser = MetadataParser()
    parser.feed(decode_source_html(raw))
    meta = parser.meta
    canonical_url = ''
    if parser.canonical:
        candidate = urljoin(url, parser.canonical)
        if safe_url(candidate) and urlsplit(candidate).hostname.lower() == urlsplit(url).hostname.lower():
            canonical_url = candidate
    # Only positively identified main-page objects can declare genre. Foreign
    # recommendation cards and unidentifiable listing objects are not evidence.
    matched_nodes = []
    def collect_identity(node, depth=0):
        if depth > 20:
            return
        if isinstance(node, list):
            for child in node:
                collect_identity(child, depth + 1)
        elif isinstance(node, dict):
            types = node.get('@type', [])
            types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
            supported = {'Article', 'NewsArticle', 'BlogPosting', 'InterviewNewsArticle',
                         'ReportageNewsArticle', 'VideoObject', 'PodcastEpisode'}
            if any(isinstance(t, str) and t in supported for t in types) and article_identity(node, url) == 'matched':
                matched_nodes.append(node)
            for key in ('@graph', 'mainEntity'):
                if key in node:
                    collect_identity(node[key], depth + 1)
    for document in parser.json_documents:
        collect_identity(document)
    genres = {declared_category(node.get('@type'), node.get('genre')) for node in matched_nodes} - {''}
    declared_genre = next(iter(genres)) if len(genres) == 1 else ''
    tag_values = []
    # Publisher sections are topical information, not article genres. Keep the
    # explicit section before keywords so it survives the bounded tag list.
    for node in matched_nodes:
        tag_values.extend(normalize_publisher_tags(node.get('articleSection', [])))
    if matched_nodes or meta.get('og:type') == 'article':
        tag_values.extend(normalize_publisher_tags(meta.get('article:section', '')))
    for node in matched_nodes:
        tag_values.extend(normalize_publisher_tags(node.get('keywords', [])))
    if matched_nodes or meta.get('og:type') == 'article':
        tag_values.extend(normalize_publisher_tags(meta.get('keywords', '')))
    tags = normalize_publisher_tags(tag_values)
    date_raw = meta.get('article:published_time') or meta.get('datepublished') or ''
    date_source = 'meta:published_time' if date_raw else ''
    if not date_raw:
        matched_dates, anonymous_dates = set(), set()
        has_matched_article = False
        has_foreign_article = False
        def collect(node, depth=0):
            nonlocal has_matched_article, has_foreign_article
            if depth > 20: return
            if isinstance(node, list):
                for child in node: collect(child, depth + 1)
            elif isinstance(node, dict):
                types = node.get('@type', [])
                if isinstance(types, str): types = [types]
                if not isinstance(types, list): types = []
                if any(t in ['Article', 'NewsArticle', 'InterviewNewsArticle', 'ReportageNewsArticle', 'BlogPosting', 'VideoObject', 'PodcastEpisode'] for t in types):
                    identity = article_identity(node, url)
                    has_matched_article |= identity == 'matched'
                    has_foreign_article |= identity == 'foreign'
                    value = node.get('datePublished')
                    if isinstance(value, str) and value.strip():
                        if identity == 'matched': matched_dates.add(value)
                        elif identity == 'anonymous': anonymous_dates.add(value)
                for key in ('@graph', 'mainEntity'):
                    if key in node: collect(node[key], depth + 1)
        for document in parser.json_documents: collect(document)
        # A positively identified article takes precedence over recommendations.
        # Anonymous data cannot identify this page when other article identities
        # are present, or repair a matched article with a missing publication date.
        values = matched_dates if has_matched_article else anonymous_dates if not has_foreign_article else set()
        if len(values) == 1:
            date_raw = values.pop(); date_source = 'jsonld:Article.datePublished'
    dt = parse_published(date_raw)
    image = meta.get('og:image') or meta.get('twitter:image') or ''
    image_source = 'meta:og:image' if meta.get('og:image') else 'meta:twitter:image' if image else ''
    image = urljoin(url, image) if image else ''
    image = image if len(image) <= 1024 and safe_url(image) else ''
    category, category_evidence = publisher_category(url, 'article' if meta.get('og:type') == 'article' else 'other')
    if declared_genre and category in ('article', 'other'):
        category = declared_genre
        category_evidence = 'Gatunek jawnie zadeklarowany w JSON-LD wydawcy dla adresu tego materiału: ' + declared_genre + '.'
    elif matched_nodes and category == 'other':
        category = 'article'
    return {'url': url, 'canonical_url': canonical_url, 'title': (meta.get('og:title') or parser.title).strip()[:500],
        'source_name': (meta.get('og:site_name') or urlparse(url).hostname or '')[:255],
        'description': (meta.get('og:description') or meta.get('description') or '')[:4000],
        'image_url': image,
        'image_source': image_source if image else '',
        'author': (meta.get('author') or '')[:200], 'published_date': dt.isoformat() if dt else None,
        'category': category, 'category_evidence': category_evidence,
        'declared_genre': declared_genre, 'tags': tags,
        'date_raw': date_raw, 'date_source': date_source, 'publisher_type': meta.get('og:type', ''),
        'warnings': ['Metadane deklaruje wydawca. Sprawdź je w źródle przed zapisaniem.'] +
            ([] if dt else ['Nie ustalono daty publikacji ze strefą czasu. Pole pozostaje puste.'])}


@extend_schema(request=inline_serializer(name='PreviewURL', fields={'url': serializers.URLField()}), responses={200: OpenApiTypes.OBJECT, 422: OpenApiTypes.OBJECT})
@api_view(['POST'])
@permission_classes([IsAdminUser])
def preview_url(request):
    url = str(request.data.get('url', '')).strip()
    if not safe_url(url) or len(url) > 1024:
        raise serializers.ValidationError({'url': 'Podaj poprawny adres HTTP lub HTTPS.'})
    if urlparse(url).hostname in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
        from news.x_reference import normalize_x_url, reference_card
        return Response({'reference': reference_card(normalize_x_url(url))})
    existing = Article.objects.filter(url=url).select_related('source', 'voting', 'official_record').first()
    if existing:
        return Response({'existing': ArticleSerializer(existing).data})
    try:
        data = extract_metadata(fetch_feed(url), url)
    except Exception:
        return Response({'detail': 'Nie udało się pobrać metadanych. Strona może blokować pobieranie. Możesz przepisać dane ze źródła ręcznie.'}, status=422)
    return Response({'metadata': data})
