# SPIN.CLINIC + PRZESZLOSC.TODAY - Infrastructure

## ARCHITECTURE

Frontend (Vercel) → API (Railway Django) → Database (PostgreSQL) + Cache (Redis) + Queue (Celery)

## HOSTING

### Railway (Backend)
- PostgreSQL 15: $5/m
- Redis 7: Included
- Django app: $5/m
- Celery worker: $5/m
- Total: ~60 PLN/m

### Vercel (Frontend)
- spin.clinic: Free tier
- przeszlosc.today: Free tier
- Total: $0

## DATABASE SCHEMA

**core_source** - Media outlets
- id, name, url, source_type, rss_url, twitter_user_id, scrape_enabled

**core_article** - News articles
- id, source_id, category, title, url, published_date, author, description, image_url, tweet_id, is_premium

**core_thread** - Curated timelines
- id, title, slug, thread_type, description, published, featured, views_count

**core_threaditem** - Articles in threads
- id, thread_id, article_id, position, editorial_note

## CELERY SCHEDULE

- GDELT: Every 2 hours
- NewsAPI: 3x daily (6:30, 12:30, 18:00)
- RSS: Every hour
- Twitter: Every 2 hours

## ENVIRONMENT VARIABLES
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
DJANGO_SECRET_KEY=random_string
DJANGO_ALLOWED_HOSTS=.railway.app,.spin.clinic,.przeszlosc.today
NEWSAPI_KEY=your_key
TWITTER_BEARER_TOKEN=your_token
CELERY_BROKER_URL=${REDIS_URL}
SENTRY_DSN=your_sentry_dsn

## DEPLOYMENT

### Backend (Railway)
railway login
railway link
railway up

### Frontend (Vercel)
cd frontend/spin-clinic
vercel --prod
vercel alias [deployment].vercel.app spin.clinic


## MONITORING

- Errors: Sentry
- Analytics: Plausible
- Logs: Railway dashboard
- Alerts: Email (scraper failures)

## SECURITY

- HTTPS: Automatic
- Rate limiting: 100 req/min
- CORS: Configured
- Backups: Daily automatic
- Secrets: Environment variables

## COST BREAKDOWN

**MVP (Month 1-3):** 60 PLN/m
**Scaled (Month 6+):** 220-300 PLN/m
**Optional APIs:** 400-2000 PLN/m (Twitter API Basic, NewsAPI Developer)

## BACKUP

- Database: Daily automatic (7 days retention)
- Manual: Weekly export to Google Drive
- Recovery time: <30 minutes

## SCALING

- Month 1-3: 1 web, 1 worker
- Month 4-6: 2 web, 2 workers (auto-scale)
- Month 7+: 3-5 web, 3 workers
