# SPIN.CLINIC + PRZESZLOSC.TODAY - Complete Project Specification

## PROJECT OVERVIEW

**Name:** spin.clinic + przeszlosc.today
**Type:** News aggregation + fact-checking platform
**Market:** Poland (10M politically active users)
**Timeline:** 4 weeks MVP, 12 months to profitability
**Stack:** Django + Next.js + PostgreSQL + Celery

**Mission:**
Context-before-content news discovery through chronological timelines.

---

## DATA SOURCES

### Aggregators (3)
- **GDELT:** 300 PL sources, free, every 2h
- **NewsAPI:** 150 PL sources, free (100 req/day), 3x daily
- **Google News RSS:** All PL media, free, on-demand

### RSS Sources (42 portals)
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
... (42 total - see full list in code)

### Government (16 institutions)
1. Senat RP - https://www.senat.gov.pl/rss/aktualnosci.xml
2. Kancelaria Prezydenta - https://www.prezydent.pl/rss/
3. NIK - https://www.nik.gov.pl/rss/
4. RPO - https://bip.brpo.gov.pl/rss
5. GUS - https://stat.gov.pl/rss/
... (16 total)

### Twitter (40 politicians)
- @AndrzejDuda (ID: 233961134)
- @donaldtusk (ID: 2548841281)
- @morawieckim (ID: 701536909381132288)
- @pisorgpl (ID: 172906058)
- @Platforma_org (ID: 15913039)
... (40 total - see full list in code)

---

## FEATURES

### Core (MVP)
1. **Search Timeline**
   - Input: Keyword + date range
   - Output: Articles grouped by date
   - Layout: Date rows with article columns (4/row)
   - Filtering: Category badges

2. **Article Box**
   - Image, badge, title, source, date
   - Hover: Scale animation
   - Click: Open modal

3. **Article Modal**
   - Full details
   - Related articles (3 items)
   - External link button

4. **Thread Detail**
   - Horizontal scrollable timeline
   - Chronological order (left→right)
   - Click to expand

5. **Homepage**
   - Featured threads (3-6 cards)
   - Different per domain

6. **Admin Panel**
   - Thread creation
   - Article selection
   - Editorial notes

### Premium (Month 2+)
- Category unlocks (tweets, mentions)
- Email alerts
- CSV/PDF export
- API access

---

## USER FLOWS

### Flow 1: Search News
1. Land on przeszlosc.today
2. Type "ZondaCrypto"
3. See timeline grid (grouped by date)
4. Click article → Modal opens
5. View related articles
6. Open source link

### Flow 2: Fact-Check
1. See tweet: "Morawiecki: Never promised 500+"
2. Open spin.clinic
3. Find thread: "Morawiecki vs 500+"
4. Browse timeline (7 items, 2016-2025)
5. Verify: He DID promise in 2016
6. Share on Twitter

### Flow 3: Admin Creates Thread
1. Login to /admin
2. Add Thread
3. Search articles
4. Select 10 articles
5. Set chronological order
6. Add editorial notes
7. Publish

---

## API ENDPOINTS

**GET /api/search/**
Query: ?q=keyword&from_date=YYYY-MM-DD&categories=article,statement
Response: { total, timeline: { "2025-01-20": [articles] } }

text


**GET /api/articles/{id}/related/**
Response: { related: [articles] }

text


**GET /api/threads/**
Response: [{ id, title, slug, items: [...] }]

text


**GET /api/threads/{slug}/**
Response: { id, title, items: [{ position, article, editorial_note }] }

text


---

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
- Lucide icons

### Infrastructure
- Railway (backend + DB)
- Vercel (frontend × 2)
- Sentry (errors)
- Plausible (analytics)

---

## REPOSITORY STRUCTURE
spin-clinic/
├── backend/
│ ├── config/
│ │ ├── settings.py
│ │ └── celery.py
│ ├── core/
│ │ ├── models.py
│ │ └── admin.py
│ ├── api/
│ │ ├── views.py
│ │ └── serializers.py
│ ├── scraper/
│ │ ├── tasks.py
│ │ └── sources_config.py
│ ├── requirements.txt
│ └── Procfile
├── frontend/
│ ├── spin-clinic/
│ │ ├── app/
│ │ ├── components/
│ │ └── package.json
│ └── przeszlosc-today/
│ └── (same structure)
└── docs/
├── roadmap.md
├── infrastructure.md
└── project.md

text


---

## DEPLOYMENT CHECKLIST

### Backend (Railway)
- [ ] Create account
- [ ] Add PostgreSQL + Redis
- [ ] Set environment variables
- [ ] Deploy from GitHub
- [ ] Run migrations
- [ ] Create superuser
- [ ] Start Celery worker

### Frontend (Vercel)
- [ ] Create account
- [ ] Import GitHub repos (×2)
- [ ] Set API URL env var
- [ ] Deploy
- [ ] Configure custom domains
- [ ] Verify SSL

---

## SUCCESS METRICS

### Week 3 (MVP Launch)
- ✅ 10 threads published
- ✅ 30,000+ articles in database
- ✅ Both domains live
- ✅ Scrapers running automatically

### Month 3
- ✅ 5,000 users/month
- ✅ 20 Patronite supporters
- ✅ 50+ threads total
- ✅ 3+ media mentions

### Month 12
- ✅ 10,000+ users/month
- ✅ 100+ paying users
- ✅ Break-even or profitable
- ✅ Recognized fact-checking tool

---

## COST ESTIMATES

**MVP (Month 1-3):**
- Infrastructure: 60 PLN/m
- Time investment: 200h
- Total cash: 180 PLN

**Scaled (Month 6+):**
- Infrastructure: 220 PLN/m
- Optional APIs: 400-2000 PLN/m
- Expected revenue: 500-3000 PLN/m

