# SPIN.CLINIC + PRZESZLOSC.TODAY - Roadmap

## OVERVIEW
4-week MVP development plan, followed by 3-month iteration cycle and 6-month scaling roadmap.

---

## WEEK 1: Backend Foundation & Data Pipeline

### Day 1-2: Infrastructure Setup (16h)
**Goal:** Production-ready backend environment

**Tasks:**
- [ ] Create Railway account
- [ ] Provision PostgreSQL 15 database
- [ ] Provision Redis 7 instance
- [ ] Setup Django 5.0 project structure
- [ ] Configure environment variables
- [ ] Create database models (Source, Article, Thread, ThreadItem)
- [ ] Run initial migrations
- [ ] Create Django superuser
- [ ] Setup Celery + Celery Beat
- [ ] Configure CORS for frontend domains

**Deliverables:**
- ✅ Live backend URL (https://[project].up.railway.app)
- ✅ Admin panel accessible
- ✅ Database schema created
- ✅ Celery worker running

**Validation:**
```bash
railway run python manage.py check
railway run python manage.py showmigrations
curl https://[project].railway.app/api/health/

Day 3: Historical Data Import (8h)
Goal: Seed database with 20,000+ historical articles

Tasks:

 Implement GDELT scraper (scraper/tasks.py)
 Configure 30 priority topics for import
 Run historical import (2015-2024)
Morawiecki, Tusk, Kaczyński, Duda (politics)
500+, CPK, NFZ, inflacja (policy)
Ukraina, NATO, UE (international)
 Monitor import progress (Railway logs)
 Verify data quality in Django admin
Deliverables:

✅ 15,000-25,000 articles imported
✅ Articles span 2015-2024 date range
✅ Data visible in admin panel
Success Metrics:

Import completion: 100%
Duplicate rate: <5%
Average articles per topic: >500
Day 4: Real-Time Scrapers (8h)
Goal: Automated daily news collection

Tasks:

 Implement NewsAPI scraper
Register free account (100 req/day)
Configure 20 daily topics
Test single topic scrape
 Implement RSS scraper
Configure 42 top Polish portals
Add 16 government institutions
Test feed parsing
 Setup Celery Beat schedule
GDELT: every 2 hours
NewsAPI: 3x daily (6:30, 12:30, 18:00)
RSS: hourly
 Add error handling & logging
Deliverables:

✅ NewsAPI integration working
✅ RSS feeds parsing correctly
✅ Celery Beat schedule active
✅ Email alerts configured for failures
Validation:

Trigger manual scrape: railway run python manage.py shell
Python

from scraper.tasks import scrape_newsapi_batch
result = scrape_newsapi_batch()
print(f"Imported: {result} articles")
Day 5: Twitter Integration (6h)
Goal: Political tweets in database

Tasks:

 Register Twitter Developer account
 Get Bearer Token (Free tier)
 Configure 40 politician accounts
Presidents: Duda
Prime Ministers: Tusk, Morawiecki
Party leaders: Kaczyński, Hołownia, Czarzasty, Biedroń, Bosak
Ministers: Sikorski, Bodnar, Nowacka, Kosiniak-Kamysz (10 total)
Influencer MPs: (20 total)
Party official accounts: (7 total)
 Implement Twitter scraper
 Add to Celery Beat (every 2h)
 Test import
Deliverables:

✅ Twitter API credentials configured
✅ 40 politicians tracked
✅ Tweets importing automatically
✅ Category badge "🐦 Post" working
Success Metrics:

Tweets/day: 200-400
API limit usage: <10,000/month (free tier)
Day 6-7: API Development (12h)
Goal: REST API for frontend consumption

Tasks:

 Implement /api/search/ endpoint
Query by keyword
Filter by date range
Filter by category
Group results by date
Pagination (500 limit)
 Implement /api/articles/<id>/related/ endpoint
Find articles ±7 days
Keyword overlap scoring
Return top 10 related
 Implement /api/threads/ viewset
List all published threads
Filter by domain (spin.clinic vs przeszlosc.today)
Thread detail with items
Increment views counter
 Write API tests
 Generate OpenAPI documentation
Deliverables:

✅ All API endpoints functional
✅ API documentation at /api/docs/
✅ Test coverage >80% for views
✅ Response times <200ms (p95)
Validation:

Bash

# Search test
curl "https://[project].railway.app/api/search/?q=Morawiecki&categories=article,statement"

# Related articles test
curl "https://[project].railway.app/api/articles/123/related/"

# Threads test
curl "https://[project].railway.app/api/threads/" -H "Host: spin.clinic"
WEEK 2: Frontend Development
Day 8-10: Core Components (24h)
Goal: Reusable UI component library

Tasks:

 Setup Next.js 14 projects (×2)
frontend/spin-clinic
frontend/przeszlosc-today
 Install dependencies
TailwindCSS, Framer Motion, React Query, Lucide icons
 Create shared components
SearchBar: Input with debounce (500ms)
TimelineGrid: Date-grouped article grid
DateRow: Sticky date header + article columns
ArticleBox: Card with image, badge, title, source, date
ArticleModal: Expanded view with related articles
LoadingSkeleton: Shimmer loading states
 Configure Tailwind theme
spin.clinic: Blue primary (#2563eb)
przeszlosc.today: Green primary (#10b981)
 Implement animations
Card hover: scale(1.03), shadow
Modal: fade + scale entrance
Timeline: staggered reveal
Deliverables:

✅ Component library built
✅ Storybook documentation (optional)
✅ Responsive design (mobile, tablet, desktop)
✅ Accessibility: ARIA labels, keyboard navigation
Design Checklist:

 Mobile-first approach
 Touch targets ≥44px
 Focus visible states
 Color contrast ≥4.5:1
Day 11-12: Search Page (16h)
Goal: Fully functional search interface

Tasks:

 Build /search page
Search input (controlled component)
Submit handler with URL params
React Query integration
Loading states
Empty states
Error states
 Implement category filters (premium tier)
Pill buttons for each category
Active/inactive states
Premium badge for locked categories
 Integrate TimelineGrid component
Fetch data from /api/search/
Group by date
Render DateRow for each date
Handle pagination (infinite scroll or load more)
 Add ArticleModal
Click ArticleBox → Open modal
Fetch related articles
External link to source
ESC key to close
Deliverables:

✅ Search page functional on both domains
✅ Results display in timeline grid
✅ Modal interactions smooth
✅ Mobile experience optimized
Performance Targets:

First Contentful Paint: <1.5s
Time to Interactive: <3s
Lighthouse score: >90
Day 13-14: Thread Pages (16h)
Goal: Homepage and thread detail views

Tasks:

 Build homepage (/)
Hero section with tagline
Featured threads grid (3-6 cards)
"Wszystkie nitki" button → /threads
Different content per domain
spin.clinic: Featured factchecks
przeszlosc.today: Featured news contexts
 Build thread detail page (/thread/[slug])
Horizontal scroll timeline
Article boxes in chronological order (left→right)
Current position indicator (dots)
Swipe gestures on mobile
Click box → Expand inline
Comments section (future, placeholder)
 Implement ThreadCard component
Thumbnail (first article image)
Thread title
Article count badge
Views counter
Date created
Click → Navigate to detail
Deliverables:

✅ Homepage live on both domains
✅ Thread detail page with horizontal timeline
✅ Smooth scrolling animations
✅ Mobile swipe working
UX Checklist:

 Scroll position persists on back navigation
 Keyboard arrow keys navigate timeline
 Touch gestures feel native
WEEK 3: Content Creation & Polish
Day 15-17: Content Curation (24h)
Goal: 10 high-quality threads ready for launch

Tasks:

 Create 5 fact-check threads (spin.clinic)

"Morawiecki vs 500+ - ewolucja stanowiska"
"Kaczyński i Obajtek - 'nie znam go osobiście'"
"Bosak o antysemityzmie - historia wypowiedzi"
"Czarzasty o koalicji z PiS - przed i po wyborach"
"Hołownia - polityk czy celebryta? Metamorfoza"
 Create 5 context threads (przeszlosc.today)

"ZondaCrypto - geneza upadku giełdy"
"Powódź 2024 - ostrzeżenia, reakcja, skutki"
"CPK - od wizji do wstrzymania"
"Ceny energii - tarcze, podwyżki, chaos"
"Wojna Rosja-Ukraina - europejska pomoc na osi czasu"
 For each thread:

 Research 10-15 source articles
 Verify dates and sources
 Write thread description (200-300 chars)
 Add editorial notes to key items
 Upload images/screenshots
 Publish and feature on homepage
Quality Standards:

Minimum 7 articles per thread
Chronological accuracy verified
Editorial notes add context (not opinion)
Sources diverse (not all from one outlet)
Day 18-19: UX Polish (16h)
Goal: Production-ready user experience

Tasks:

 Implement loading states
Skeleton screens for timeline grid
Shimmer animation
Spinner for modals
 Implement error states
Network error: Retry button
No results: Helpful message + suggestions
404 page: Search shortcut
 Add micro-interactions
Button hover states
Ripple effects on click
Toast notifications for actions
 Optimize images
Next.js Image component
Lazy loading
WebP format
Blurhash placeholders
 Performance audit
Lighthouse CI
Fix render-blocking resources
Code splitting
Bundle size optimization
 Accessibility audit
Screen reader testing
Keyboard-only navigation
Focus trap in modals
ARIA live regions for dynamic content
Deliverables:

✅ Lighthouse score >90 (all metrics)
✅ No console errors
✅ WCAG 2.1 AA compliant
✅ Works in Chrome, Firefox, Safari, Edge
Day 20: Beta Testing (8h)
Goal: Identify and fix critical issues

Tasks:

 Recruit 5-10 beta testers
 Prepare testing checklist
 Conduct user tests (1h each)
 Prioritize feedback
 Fix critical issues
 Re-test with 2-3 users
Deliverables:

✅ 10+ bugs identified and fixed
✅ UX improvements implemented
✅ Beta testers approve launch readiness
Day 21: Launch 🚀
Goal: Go-live readiness

Tasks:

 Final deployment checks
 Setup monitoring
 Prepare launch content
 Final smoke tests
 Publish and promote
Launch Checklist:

 All 10 threads published and featured
 Database has 30,000+ articles
 Scrapers running automatically
 No critical bugs in last 48h
MONTH 2-3: Iteration & Growth
Week 5-6: Premium Tier Implementation
Design paywall UI
Integrate Patronite
Implement premium checks
Add premium features
Week 7-8: Performance & SEO
Fuzzy deduplication
Database optimization
SEO improvements
Content expansion
Week 9-12: Community Building
Weekly content cadence
Influencer partnerships
User feedback loop
Media outreach
Success Metrics:

5,000 unique users/month
20 Patronite supporters
3+ media mentions
MONTH 4-6: Scale & Automate
Month 4: User Accounts & UGC
User registration
Thread creation UI
Moderation system
Launch "Wykopalisko"
Month 5: Advanced Features
Email alerts
Export functionality
Advanced search
Mobile app (React Native)
Month 6: Expansion
Evaluate Czech/Slovak markets
Business sustainability
Break-even target
Success Metrics:

10,000 users/month
100+ paying users
Break-even or profitable
KEY MILESTONES
Milestone	Target Date	Success Criteria
MVP Launch	Week 3	10 threads, 30k articles, 2 domains live
First 1k Users	Month 2	1000 unique visitors/month
Break-even	Month 6	Revenue ≥ costs (2.5k PLN/m)
10k Users	Month 9	10,000 unique visitors/month
Profitability	Month 12	5k PLN/m profit
SUCCESS DEFINITION
MVP Success (3 months):

✅ 5,000 users/month
✅ 20 Patronite supporters
✅ 50+ threads published
✅ 3+ media mentions
Long-term Success (12 months):

✅ 10,000+ users/month
✅ 100+ paying users
✅ Break-even or profitable
✅ Recognition as top fact-checking tool in Poland
