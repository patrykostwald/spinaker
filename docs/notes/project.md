# SPIN.CLINIC + PRZESZLOSC.TODAY - Project Specification

## OVERVIEW

**Name:** spin.clinic + przeszlosc.today
**Type:** News aggregation + fact-checking
**Market:** Poland (10M politically active users)
**Timeline:** 4 weeks MVP, 12 months to profitability
**Stack:** Django + Next.js + PostgreSQL + Celery

## DATA SOURCES

### Aggregators (3)
- GDELT: 300 PL sources, free, every 2h
- NewsAPI: 150 PL sources, free (100 req/day), 3x daily
- Google News RSS: All PL media, free, on-demand

### RSS Sources (42)
1. Onet - https://www.onet.pl/informacje/rss
2. Wirtualna Polska - https://wiadomosci.wp.pl/rss.xml
3. TVN24 - https://tvn24.pl/najwazniejsze.xml
4. Interia - https://fakty.interia.pl/feed
5. Polsat News - https://www.polsatnews.pl/rss/polska.xml
6. RMF24 - https://www.rmf24.pl/fakty/rss
7. Radio ZET - https://www.radiozet.pl/rss/news.xml
8. Money.pl - https://www.money.pl/rss/
9. Bankier.pl - https://www.bankier.pl/rss/wiadomosci.xml
10. TVP Info - https://www.tvp.info/rss/wiadomosci
11. Gazeta.pl - https://rss.gazeta.pl/pub/rss/gazetapl_wiadomosci.xml
12. Rzeczpospolita - https://www.rp.pl/rss/1019.xml
13. Polityka - https://www.polityka.pl/rss.xml
14. Newsweek - https://www.newsweek.pl/rss.xml
15. OKO.press - https://oko.press/feed/
16. Konkret24 - https://konkret24.tvn24.pl/feed
17. Demagog - https://demagog.org.pl/feed/
18-42. (Full list in code - 42 total)

### Government Institutions (16)
1. Senat RP - https://www.senat.gov.pl/rss/aktualnosci.xml
2. Kancelaria Prezydenta - https://www.prezydent.pl/rss/
3. NIK - https://www.nik.gov.pl/rss/
4. RPO - https://bip.brpo.gov.pl/rss
5. GUS - https://stat.gov.pl/rss/
6-16. (Full list in code)

### Twitter (40 politicians)
- AndrzejDuda (ID: 233961134)
- donaldtusk (ID: 2548841281)
- morawieckim (ID: 701536909381132288)
- (37 more - full list in code)

## FEATURES

### Core (MVP)
1. Search Timeline - Articles grouped by date
2. Article Box - Card with image, title, source, date
3. Article Modal - Full details + related articles
4. Thread Detail - Horizontal scrollable timeline
5. Homepage - Featured threads
6. Admin Panel - Thread creation

### Premium (Month 2+)
- Category unlocks (tweets, mentions)
- Email alerts
- CSV/PDF export
- API access

## USER FLOWS

### Search News
1. Land on przeszlosc.today
2. Type keyword
3. See timeline grid
4. Click article → Modal
5. View related
6. Open source

### Fact-Check
1. See politician tweet
2. Open spin.clinic
3. Find relevant thread
4. Browse timeline
5. Verify claim
6. Share

### Admin Creates Thread
1. Login /admin
2. Add Thread
3. Search articles
4. Select 10 items
5. Set order
6. Add notes
7. Publish

## API ENDPOINTS

**GET /api/search/**
Query: ?q=keyword&from_date=YYYY-MM-DD&categories=article,statement
Response: { total, timeline: { "2025-01-20": [articles] } }

**GET /api/articles/{id}/related/**
Response: { related: [articles] }

**GET /api/threads/**
Response: [{ id, title, slug, items }]

**GET /api/threads/{slug}/**
Response: { id, title, items: [{ position, article, editorial_note }] }

## TECH STACK

### Backend
- Django 5.0 + DRF
- PostgreSQL 15
- Redis 7
- Celery 5.3
- Gunicorn

### Frontend
- Next.js 14
- TailwindCSS 3.4
- Framer Motion
- React Query

### Infrastructure
- Railway (backend)
- Vercel (frontend × 2)
- Sentry (errors)
- Plausible (analytics)

## REPOSITORY STRUCTURE

```
spin-clinic/
├── backend/
│   ├── config/
│   ├── core/
│   ├── api/
│   ├── scraper/
│   └── requirements.txt
├── frontend/
│   ├── spin-clinic/
│   └── przeszlosc-today/
└── docs/
    ├── roadmap.md
    ├── infrastructure.md
    └── project.md
```

## SUCCESS METRICS

### Week 3 (MVP)
- 10 threads published
- 30,000+ articles
- Both domains live
- Scrapers running

### Month 3
- 5,000 users/month
- 20 Patronite supporters
- 50+ threads
- 3+ media mentions

### Month 12
- 10,000+ users/month
- 100+ paying users
- Break-even or profitable

## COSTS

**MVP:** 60 PLN/m infrastructure
**Scaled:** 220-300 PLN/m
**Optional APIs:** 400-2000 PLN/m



