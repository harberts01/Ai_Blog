# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Blog Daily (aiblogdaily.com) — a full-stack web app that aggregates AI-generated blog posts from five providers (ChatGPT, Claude, Gemini, Grok, Llama) and lets users compare them via blind head-to-head voting. Monetized with Stripe subscriptions (free tier: 5 posts/month with 14-day delay).

## Tech Stack

- **Backend**: Python 3.8+ / Flask / Gunicorn+Gevent
- **Database**: PostgreSQL (psycopg2, no ORM — raw parameterized SQL)
- **Frontend**: Jinja2 SSR + Bootstrap 5 + vanilla JS (no SPA framework)
- **AI APIs**: OpenAI, Anthropic, Google Generative AI, xAI (Grok), Together AI (Llama)
- **Payments**: Stripe (checkout sessions, webhooks, subscription sync)
- **Email**: Mailgun API (primary), multi-provider SMTP support

## Commands

```bash
# Run dev server
python app.py

# Run production server (as in Procfile)
gunicorn --bind 0.0.0.0:${PORT:-8080} app:app

# Run tests (requires TEST_DATABASE_URL or TEST_DB_NAME env var pointing to a test DB)
pytest tests/

# Run a single test file
pytest tests/test_vote_pipeline.py

# Run a single test
pytest tests/test_vote_pipeline.py::test_function_name -v

# Run database migrations
python run_migration.py

# Seed database
python seed_database.py
python seed_matchups.py
```

## Architecture

### Core modules (flat structure, no packages)

| File | Purpose |
|---|---|
| `app.py` (~2700 lines) | All Flask routes: public, auth, user, admin, cron, API, dashboard, comparison |
| `database.py` (~5000 lines) | All DB operations — queries, inserts, aggregations. Functions called from routes. |
| `config.py` | Environment-based config: DB connection, API keys, subscription settings, AI tool registry |
| `auth.py` | Decorators: `login_required`, `admin_required`, `premium_required` + session helpers |
| `ai_generators.py` | Provider-specific content generation (one function per AI provider) |
| `stripe_utils.py` | Stripe checkout, webhook handling, subscription management |
| `email_utils.py` | Mailgun/SMTP email dispatch |
| `utils.py` | Input sanitization (`sanitize_input`, `sanitize_html`), validation helpers |
| `schema.sql` | Base PostgreSQL schema (~15 tables) |
| `migrations/` | Numbered SQL migration files (002–013) |

### Route organization in app.py

Routes are grouped by prefix/purpose: SEO (`/robots.txt`, `/sitemap.xml`), public (`/`, `/search`, `/tool/<slug>`, `/post/<id>`), auth (`/login`, `/register`), user account (`/account`, `/billing`, `/bookmarks`, `/notifications`), pricing/checkout (`/pricing`, `/checkout/*`), admin (`/admin/*`), cron (`/cron/*` — require CRON_SECRET token), dashboard/analytics (`/dashboard/*`), comparison (`/compare/*`), and API endpoints (`/api/*`).

### Key data flows

1. **Content generation**: Cron job → `POST /cron/generate-posts/<tool_slug>` → `ai_generators.py` → saves Post to DB
2. **Voting**: User views blind matchup → `POST /api/matchups/<id>/votes` → validates eligibility → records vote + vote_event audit → updates results
3. **Subscriptions**: Pricing page → Stripe checkout session → `/checkout/success` callback → `/webhooks/stripe` confirms → DB subscription status updated → `is_user_premium()` gates access

### Database patterns

- No ORM: all queries are raw SQL with `%s` parameterized placeholders (psycopg2)
- `RealDictCursor` used throughout for dictionary-style results
- Each `database.py` function opens its own connection (no connection pooling)
- Migrations are sequential SQL files run via `run_migration.py`
- Mixed column naming: legacy tables use PascalCase (`Title`, `Content`, `CreatedAt`), newer tables use snake_case

### Frontend patterns

- Single `static/css/styles.css` file for all styles
- Dark/light mode via CSS custom properties with `localStorage` persistence
- Template inheritance from `base.html`; reusable partials in `templates/components/`
- Custom Jinja filters: `reading_time`, `word_count`
- Global template variables injected via `inject_globals()` context processor

### Security

- CSRF via Flask-WTF on all state-changing routes
- Rate limiting via Flask-Limiter (IP whitelist for cron); storage backend configurable via `RATE_LIMIT_STORAGE_URI` env var (default: `memory://`, use `redis://` in production)
- Session-based auth with secure cookie settings (HTTPONLY, SECURE, SAMESITE=Lax)
- Security headers: nonce-based CSP (with `'unsafe-inline'` fallback for inline event handlers), X-Frame-Options, X-Content-Type-Options
- HTML sanitization via `bleach` — AI-generated content is sanitized through `sanitize_html()` in `utils.py` before DB insert (whitelist of safe tags, strips `<script>`, `<iframe>`, event handlers)
- Cron endpoints accept `Authorization: Bearer <token>` header (preferred) or `?token=` query param (legacy); token validated via `_verify_cron_token()` helper
- All public `/api/*` endpoints rate-limited to 60 requests/minute per IP

## Testing

Tests use pytest with a PostgreSQL test database. The `conftest.py` sets up a `ConnectionProxy` that wraps each test in a savepoint-based transaction that rolls back after the test. Set `TEST_DATABASE_URL` or individual `DB_*` env vars with `TEST_DB_NAME` to point at the test database. Schema and migrations are applied once per session via the `db_schema` fixture.

## Environment

All secrets and config live in `.env` (never committed). Key variables: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, API keys for each AI provider, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `MAILGUN_API_KEY`, `CRON_SECRET`, `RATE_LIMIT_STORAGE_URI` (optional, defaults to `memory://`), feature flags (`MAIL_ENABLED`, `NOTIFICATIONS_ENABLED`, `BOOTSTRAP_FREE_VOTING_ENABLED`).
