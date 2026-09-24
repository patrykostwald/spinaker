import json
from pathlib import Path
import requests
from django.conf import settings
from django.utils import timezone
from news.models import Source
from scraper.catalog import TWITTER_POLITICIANS
from scraper.utils import guarded, get_or_create_source, upsert_article, reserve_budget

TWITTER_API = 'https://api.x.com/2/users/{user_id}/tweets'

@guarded
def scrape_twitter_politicians():
    if not settings.TWITTER_ENABLED or not settings.TWITTER_BEARER_TOKEN:
        return 0
    accounts = TWITTER_POLITICIANS
    if settings.TWITTER_API_TIER == 'basic':
        extended = json.loads(Path(__file__).with_name('extended_politicians.json').read_text(encoding='utf-8-sig'))
        accounts = {**accounts, **extended}
    headers = {'Authorization': f'Bearer {settings.TWITTER_BEARER_TOKEN}'}
    return sum(_scrape_user(username, data.get('user_id', ''), headers) for username, data in accounts.items())

@guarded
def _scrape_user(username, supplied_id, headers):
    source = Source.objects.filter(url=f'https://x.com/{username}').first()
    if source and (not source.scrape_enabled or not source.is_active):
        return 0
    # Resolve authoritative identity instead of trusting stale IDs from the brief.
    if not source:
        response = requests.get(f'https://api.x.com/2/users/by/username/{username}', headers=headers, timeout=(5, 30))
        response.raise_for_status()
        identity = response.json()['data']
        source = get_or_create_source(name=identity['name'], url=f'https://x.com/{username}',
            source_type='politician', twitter_user_id=identity['id'])
    from django.core.cache import cache
    from datetime import timedelta
    budget = 'twitter:' + timezone.now().strftime('%Y-%m')
    params = {'max_results': 10, 'tweet.fields': 'created_at,public_metrics,attachments',
        'expansions': 'attachments.media_keys', 'media.fields': 'url,preview_image_url'}
    if source.last_tweet_id:
        params['since_id'] = source.last_tweet_id
    else:
        params['start_time'] = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    total, ids = 0, []
    while True:
        if not reserve_budget(budget, 10, settings.TWITTER_MONTHLY_READ_LIMIT, 35 * 86400):
            Source.objects.filter(pk=source.pk).update(last_error='Wyczerpany limit pobrań X. Import niekompletny; kursor zachowany.')
            return total
        try:
            response = requests.get(TWITTER_API.format(user_id=source.twitter_user_id), headers=headers, params=params.copy(), timeout=(5, 30))
            response.raise_for_status()
            payload = response.json()
            if payload.get('errors'):
                raise ValueError('X returned incomplete data')
        except Exception as exc:
            Source.objects.filter(pk=source.pk).update(last_error=type(exc).__name__)
            raise
        tweets = payload.get('data') or []
        cache.decr('budget:' + budget, max(0, 10 - len(tweets)))
        media = {m['media_key']: m.get('url') or m.get('preview_image_url', '') for m in payload.get('includes', {}).get('media', [])}
        for tweet in tweets:
            tweet_id = tweet.get('id')
            if not tweet_id or not tweet.get('text'):
                raise ValueError('Incomplete X record; cursor not advanced')
            metrics = tweet.get('public_metrics') or {}
            keys = tweet.get('attachments', {}).get('media_keys', [])
            _, created = upsert_article(source=source, title=tweet['text'], description=tweet['text'],
                author=source.name, url=f'https://x.com/{username}/status/{tweet_id}', published_date=tweet.get('created_at'),
                category='tweet', ingestion_method='x', category_reviewed=False, tweet_id=tweet_id, likes_count=metrics.get('like_count', 0),
                retweets_count=metrics.get('retweet_count', 0), image_url=media.get(keys[0], '') if keys else '')
            total += created
            ids.append(int(tweet_id))
        token = payload.get('meta', {}).get('next_token')
        if not token:
            break
        params['pagination_token'] = token
    if ids:
        source.last_tweet_id = str(max(ids))
    source.last_scraped = timezone.now()
    source.last_error = ''
    source.save(update_fields=['last_tweet_id', 'last_scraped', 'last_error'])
    return total
