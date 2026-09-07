```markdown
# SPIN.CLINIC + PRZESZLOSC.TODAY - Infrastructure Documentation

## ARCHITECTURE OVERVIEW
┌─────────────────────────────────────────────────────────────┐
│ USERS │
└────────────────────┬────────────────────────────────────────┘
│
┌────────▼────────┐ ┌─────▼──────┐
│ spin.clinic │ │ przeszlosc │
│ (Vercel) │ │ .today │
│ Next.js 14 │ │ (Vercel) │
└────────┬────────┘ └─────┬──────┘
│ │
└──────────────────┴───────────────────┘
│
┌─────────────▼──────────────┐
│ API Gateway │
│ (Railway - Django) │
└─────────────┬──────────────┘
│
┌─────────▼─────────┐ ┌─────▼──────┐ ┌───────▼────────┐
│ PostgreSQL 15 │ │ Redis 7 │ │ Celery Worker │
│ (Railway) │ │ (Railway) │ │ + Beat │
└────────────────────┘ └────────────┘ └────────────────┘
---

## HOSTING INFRASTRUCTURE

### Railway.app (Backend)

**Services:**
1. PostgreSQL Database
   - Version: 15.x
   - Storage: 10GB (MVP) → 50GB (Month 6)
   - Backups: Daily automatic
   - Cost: $5/m (shared) → $15/m (dedicated)

2. Redis Cache
   - Version: 7.x
   - Memory: 256MB → 1GB
   - Cost: Included ($5/m)

3. Django Application
   - Python 3.11
   - Gunicorn (4 workers)
   - Auto-deploy from GitHub
   - Cost: $5-10/m

4. Celery Worker + Beat
   - Concurrency: 4 workers
   - Memory: 512MB
   - Cost: $5/m

**Environment Variables:**
```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
DJANGO_SECRET_KEY=random_string
DJANGO_ALLOWED_HOSTS=.railway.app,.spin.clinic,.przeszlosc.today
NEWSAPI_KEY=your_key
TWITTER_BEARER_TOKEN=your_token
CELERY_BROKER_URL=${REDIS_URL}
SENTRY_DSN=your_sentry_dsn

