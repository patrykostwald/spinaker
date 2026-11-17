# SPIN.CLINIC + PRZESZLOSC.TODAY - Roadmap

## OVERVIEW
4-week MVP development plan, followed by 3-month iteration cycle and 6-month scaling roadmap.

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
- Live backend URL (https://[project].up.railway.app)
- Admin panel accessible
- Database schema created
- Celery worker running

### Day 3: Historical Data Import (8h)
**Goal:** Seed database with 20,000+ historical articles

**Tasks:**
- [ ] Implement GDELT scraper
- [ ] Configure 30 priority topics for import
- [ ] Run historical import (2015-2024)
- [ ] Monitor import progress
- [ ] Verify data quality in Django admin

**Deliverables:**
- 15,000-25,000 articles imported
- Articles span 2015-2024 date range
- Data visible in admin panel

### Day 4: Real-Time Scrapers (8h)
**Goal:** Automated daily news collection

**Tasks:**
- [ ] Implement NewsAPI scraper
- [ ] Implement RSS scraper (42 portals + 16 institutions)
- [ ] Setup Celery Beat schedule
- [ ] Add error handling & logging

**Deliverables:**
- NewsAPI integration working
- RSS feeds parsing correctly
- Celery Beat schedule active
- Email alerts configured

### Day 5: Twitter Integration (6h)
**Goal:** Political tweets in database

**Tasks:**
- [ ] Register Twitter Developer account
- [ ] Get Bearer Token (Free tier)
- [ ] Configure 40 politician accounts
- [ ] Implement Twitter scraper
- [ ] Add to Celery Beat (every 2h)

**Deliverables:**
- Twitter API credentials configured
- 40 politicians tracked
- Tweets importing automatically
- Category badge working

### Day 6-7: API Development (12h)
**Goal:** REST API for frontend consumption

**Tasks:**
- [ ] Implement /api/search/ endpoint
- [ ] Implement /api/articles/id/related/ endpoint
- [ ] Implement /api/threads/ viewset
- [ ] Write API tests
- [ ] Generate OpenAPI documentation

**Deliverables:**
- All API endpoints functional
- API documentation available
- Test coverage >80%
- Response times <200ms

## WEEK 2: Frontend Development

### Day 8-10: Core Components (24h)
**Goal:** Reusable UI component library

**Tasks:**
- [ ] Setup Next.js 14 projects (spin-clinic + przeszlosc-today)
- [ ] Install dependencies (TailwindCSS, Framer Motion, React Query)
- [ ] Create shared components (SearchBar, TimelineGrid, DateRow, ArticleBox, ArticleModal)
- [ ] Configure Tailwind theme
- [ ] Implement animations

**Deliverables:**
- Component library built
- Responsive design working
- Accessibility features implemented

### Day 11-12: Search Page (16h)
**Goal:** Fully functional search interface

**Tasks:**
- [ ] Build /search page
- [ ] Implement category filters
- [ ] Integrate TimelineGrid component
- [ ] Add ArticleModal

**Deliverables:**
- Search page functional on both domains
- Results display in timeline grid
- Modal interactions smooth
- Mobile experience optimized

### Day 13-14: Thread Pages (16h)
**Goal:** Homepage and thread detail views

**Tasks:**
- [ ] Build homepage (different per domain)
- [ ] Build thread detail page (horizontal timeline)
- [ ] Implement ThreadCard component

**Deliverables:**
- Homepage live on both domains
- Thread detail page with horizontal timeline
- Smooth scrolling animations
- Mobile swipe working

## WEEK 3: Content Creation & Polish

### Day 15-17: Content Curation (24h)
**Goal:** 10 high-quality threads ready for launch

**Tasks:**
- [ ] Create 5 fact-check threads (spin.clinic)
- [ ] Create 5 context threads (przeszlosc.today)
- [ ] Research 10-15 source articles per thread
- [ ] Verify dates and sources
- [ ] Write thread descriptions
- [ ] Add editorial notes
- [ ] Publish and feature on homepage

### Day 18-19: UX Polish (16h)
**Goal:** Production-ready user experience

**Tasks:**
- [ ] Implement loading states
- [ ] Implement error states
- [ ] Add micro-interactions
- [ ] Optimize images
- [ ] Performance audit
- [ ] Accessibility audit

**Deliverables:**
- Lighthouse score >90
- No console errors
- WCAG 2.1 AA compliant

### Day 20: Beta Testing (8h)
**Goal:** Identify and fix critical issues

**Tasks:**
- [ ] Recruit 5-10 beta testers
- [ ] Prepare testing checklist
- [ ] Conduct user tests
- [ ] Prioritize feedback
- [ ] Fix critical issues
- [ ] Re-test

### Day 21: Launch
**Goal:** Go-live

**Tasks:**
- [ ] Final deployment checks
- [ ] Setup monitoring (Sentry, Plausible)
- [ ] Prepare launch content
- [ ] Final smoke tests
- [ ] Publish and promote

## MONTH 2-3: Iteration & Growth

### Week 5-6: Premium Tier
- Design paywall UI
- Integrate Patronite
- Implement premium checks
- Add premium features

### Week 7-8: Performance & SEO
- Fuzzy deduplication
- Database optimization
- SEO improvements
- Content expansion

### Week 9-12: Community Building
- Weekly content cadence
- Influencer partnerships
- User feedback loop
- Media outreach

**Success Metrics:**
- 5,000 unique users/month
- 20 Patronite supporters
- 3+ media mentions

## MONTH 4-6: Scale & Automate

### Month 4: User Accounts & UGC
- User registration
- Thread creation UI
- Moderation system
- Launch Wykopalisko

### Month 5: Advanced Features
- Email alerts
- Export functionality
- Advanced search
- Mobile app

### Month 6: Expansion
- Evaluate Czech/Slovak markets
- Business sustainability
- Break-even target

**Success Metrics:**
- 10,000 users/month
- 100+ paying users
- Break-even or profitable

## KEY MILESTONES

| Milestone | Target Date | Success Criteria |
|-----------|-------------|------------------|
| MVP Launch | Week 3 | 10 threads, 30k articles, 2 domains live |
| First 1k Users | Month 2 | 1000 unique visitors/month |
| Break-even | Month 6 | Revenue ≥ costs |
| 10k Users | Month 9 | 10,000 unique visitors/month |
| Profitability | Month 12 | 5k PLN/m profit |

## SUCCESS DEFINITION

**MVP Success (3 months):**
- 5,000 users/month
- 20 Patronite supporters
- 50+ threads published
- 3+ media mentions

**Long-term Success (12 months):**
- 10,000+ users/month
- 100+ paying users
- Break-even or profitable
- Recognition as top fact-checking tool in Poland
