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
