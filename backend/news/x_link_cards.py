"""Plain text X cards: local posts first, public oEmbed second; never the paid API."""
import re
from datetime import datetime, timezone as dt_timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit
import requests
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from news.community_models import CommunityLink


def x_post(value):
    try:
        url = urlsplit(value)
        match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/([1-9][0-9]{0,18})/?', url.path)
        if url.scheme in ('http', 'https') and url.hostname in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com') and match:
            return match.group(2), f'https://x.com/{match.group(1)}/status/{match.group(2)}'
    except ValueError:
        pass
    return None


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_p = False
        self.text = []
        self.date = []
        self.in_date = False
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1
        if tag == 'p':
            self.in_p = True
        if tag == 'br' and self.in_p:
            self.text.append(' ')
        if tag == 'a' and not self.in_p and '/status/' in dict(attrs).get('href', ''):
            self.in_date = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignored = max(0, self.ignored - 1)
        if tag == 'p':
            self.in_p = False
        if tag == 'a':
            self.in_date = False

    def handle_data(self, data):
        if not self.ignored:
            if self.in_p:
                self.text.append(data)
            elif self.in_date:
                self.date.append(data)


def stored_post_data(post):
    from news.clinic import published_diagnoses
    diagnosis = published_diagnoses().filter(post=post).first()
    return {'box_type': 'post', 'body': post.text[:280], 'source_name': post.account.display_name,
        'x_handle': post.account.handle.lstrip('@'), 'published_date': post.published_at.isoformat(),
        'diagnosis_id': diagnosis.pk if diagnosis else None, 'intensity': diagnosis.intensity if diagnosis else None}


def card_data(link):
    """Refresh diagnosis/availability from the DB at read time; don't expose withdrawn content."""
    parsed = x_post(link.canonical_url)
    if not parsed:
        return {}
    from news.political_models import PoliticalPost
    post = PoliticalPost.objects.select_related('account').filter(post_id=parsed[0]).first()
    if post:
        return stored_post_data(post) if post.available else {'title': 'Wpis niedostępny'}
    return link.x_data


def resolve_x(url, user, title=''):
    from news.political_models import PoliticalPost
    parsed = x_post(url)
    if not parsed:
        return None
    post_id, canonical = parsed
    # Identity is the status ID even if a pasted handle is old or incorrect.
    post = PoliticalPost.objects.select_related('account').filter(post_id=post_id).first()
    if post:
        canonical = f'https://x.com/{post.account.handle.lstrip("@")}/status/{post_id}'
    existing = CommunityLink.objects.filter(canonical_url__regex=rf'/status/{post_id}$').first()
    if existing and existing.hidden_at:
        return {'blocked': True}
    if existing and existing.x_fetched_at and existing.x_fetched_at > timezone.now() - timedelta(days=1):
        return {'link': existing}
    data = stored_post_data(post) if post and post.available else {}
    if not post and not cache.get('x-oembed-failed:' + post_id):
        try:
            response = requests.get('https://publish.twitter.com/oembed', params={
                'url': canonical, 'omit_script': 1, 'dnt': 'true'}, timeout=(3, 8), allow_redirects=False)
            if response.status_code in (301, 302, 307, 308):
                target = urlsplit(response.headers.get('Location', ''))
                if target.scheme != 'https' or target.hostname != 'publish.x.com' or target.path != '/oembed':
                    raise ValueError('Unexpected oEmbed redirect')
                response = requests.get('https://publish.x.com/oembed', params={
                    'url': canonical, 'omit_script': 1, 'dnt': 'true'}, timeout=(3, 8), allow_redirects=False)
            response.raise_for_status()
            raw = response.json()
            parser = TextParser()
            parser.feed(str(raw.get('html', ''))[:50000])
            body = ''.join(parser.text).strip()[:280]
            author_url = urlsplit(str(raw.get('author_url', '')))
            handle = author_url.path.strip('/')
            if not body or author_url.hostname not in ('twitter.com', 'x.com') or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
                raise ValueError('Invalid oEmbed')
            try:
                published = datetime.strptime(''.join(parser.date), '%B %d, %Y').replace(tzinfo=dt_timezone.utc).isoformat()
            except ValueError:
                published = None
            data = {'box_type': 'post', 'body': body, 'source_name': str(raw.get('author_name', handle))[:150],
                'x_handle': handle, 'published_date': published}
        except (requests.RequestException, ValueError, TypeError, KeyError):
            cache.set('x-oembed-failed:' + post_id, True, 600)
    if not data and not title and not existing:
        return {'needs_title': True}
    canonical = existing.canonical_url if existing else canonical
    defaults = {'domain': 'x.com',
            'title': data.get('body') or title or (existing.title if existing else 'Wpis na X'),
            'title_origin': 'publisher' if data else 'reader', 'x_data': data,
            'x_fetched_at': timezone.now(), 'submitted_by': existing.submitted_by if existing else user}
    try:
        with transaction.atomic():
            link, _ = CommunityLink.objects.update_or_create(canonical_url=canonical, defaults=defaults)
    except IntegrityError:
        link = CommunityLink.objects.get(canonical_url=canonical)
    return {'link': link}
