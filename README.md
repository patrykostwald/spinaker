# spin.clinic · przeszłość.today

Two public-interest products on one codebase, built by [iapply](https://iapply.pl).

- **[spin.clinic](https://spin.clinic)** shows how political messages are built. Dr. Spin, an AI analyst, tags persuasion techniques in politicians' posts and checks each claim against sources. The same yardstick applies to everyone.
- **[przeszłość.today](https://przeszlosc.today)** puts public figures on one timeline: statements, Sejm votes, companies from the KRS register and public money, with every link backed by a source. Public persons and entities only.

## Architecture

| Layer | Technology |
|---|---|
| API and domain logic | Django 5, Django REST Framework, drf-spectacular |
| Background work | Celery and Redis: source harvesters, daily analysis, cache warm-up |
| Data | PostgreSQL |
| Frontends | Next.js 14 and React 18: `frontend-spin`, `frontend-przeszlosc` |
| AI | Structured LLM outputs, reviewed by a council of independent models before publication |
| Delivery | Docker Compose behind Caddy, GitHub Actions for CI |

Every automated result is a proposal with evidence. Publication passes deterministic gates: source checks, identity safeguards for people and a human review where the stakes require it.

## Repository layout

```
backend/              Django project: apps, harvesters, analysis pipeline, tests
frontend-spin/        spin.clinic web app
frontend-przeszlosc/  przeszłość.today web app
packages/             shared code
deploy/               production compose file, Caddy config, backup and runbooks
docs/                 architecture notes and audits
scripts/              local tooling (scripts/windows: workstation helpers)
docs/notes/           earlier planning notes and handoff documents
```

## Running locally

```bash
cp .env.example .env
docker compose up --build
```

Backend tests:

```bash
cd backend
pytest
```

Tests run offline by default: a guard blocks outgoing network calls, so no real API is hit during a test run.

## Data and privacy

Only publicly available sources with a lawful basis are used. Private individuals are not profiled. Each connection shown in przeszłość.today points to its source document.

## Status

Both products are live. Active development happens on feature branches and is merged through pull requests.

## License

All rights reserved. © iapply sp. z o.o.
