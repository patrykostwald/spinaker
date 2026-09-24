"""Bounded confirmation of an explicitly linked RSS/Atom channel.

This is evidence collection only.  It neither changes a Source nor creates an
access card.  Every request goes through ProbeNetwork, including robots and
certificate checks.
"""
from urllib.parse import urljoin

import feedparser

from news.metadata import decode_source_html
from scraper.source_probe import ProbeError, PublisherLinks, public_link


CHANNEL_DISCOVERY_VERSION = 1


def explicit_feed_links(base_url, parser):
    links = []
    for item in parser.links:
        url = public_link(urljoin(base_url, item['href']))
        if not url:
            continue
        indicator = f"{url} {item.get('type', '')} {item.get('text', '')}".lower()
        if any(token in indicator for token in ('rss', 'atom', '/feed', 'feed.xml')):
            links.append(url)
    return list(dict.fromkeys(links))[:6]


def inspect_explicit_channel(source, state, network):
    """Inspect source and previously recorded official terms pages for feed links."""
    result = {'version': CHANNEL_DISCOVERY_VERSION, 'status': 'no_explicit_channel_found',
              'pages_checked': [], 'channels': [], 'error': ''}
    discovery = (state or {}).get('legal_terms_discovery') or {}
    pages = [source.url] + [page.get('url') for page in discovery.get('terms_pages', []) if page.get('url')]
    for page_url in list(dict.fromkeys(url for url in pages if url))[:3]:
        try:
            raw, final_url, _ = network.fetch(page_url)
            parser = PublisherLinks(); parser.feed(decode_source_html(raw))
            result['pages_checked'].append({'url': final_url, 'status': 'ok'})
            for channel in explicit_feed_links(final_url, parser):
                if any(item['url'] == channel for item in result['channels']):
                    continue
                try:
                    feed_raw, feed_url, _ = network.fetch(channel)
                    parsed = feedparser.parse(feed_raw)
                    usable = [entry for entry in parsed.get('entries', [])
                              if str(entry.get('title', '')).strip() and public_link(entry.get('link', ''))]
                    result['channels'].append({'url': feed_url, 'status': 'working' if usable else 'empty',
                                               'usable_entry_count': len(usable)})
                except Exception as exc:
                    error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
                    result['channels'].append({'url': channel, 'status': 'error', 'error': error})
        except Exception as exc:
            error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
            result['pages_checked'].append({'url': page_url, 'status': 'error', 'error': error})
    if any(item['status'] == 'working' for item in result['channels']):
        result['status'] = 'working_channel_requires_editorial_card_review'
    elif result['channels']:
        result['status'] = 'explicit_channel_unusable'
    elif result['pages_checked'] and all(page['status'] == 'error' for page in result['pages_checked']):
        result['status'] = 'unavailable'
    return result
