# Document 02 - Technical Requirements Document

## Current Frontend

Streamlit with Python 3.11.

The current app is optimized for rapid product validation, demo testing, and local/cloud Streamlit deployment.

## Future Frontend Direction

For SaaS scale, migrate the customer-facing app to a production web stack such as Next.js with TypeScript and a component system. Streamlit can remain an internal prototype/admin surface until the SaaS frontend is ready.

## Current Backend

Python service modules inside the same repository:

- `application_service.py` for the end-to-end application workflow.
- `job_discovery.py` for provider-neutral job discovery.
- `job_preferences.py` for profile-based search intent.
- `job_fetcher.py` and `job_search.py` for URL ingestion and ranking.
- `analyzer.py`, `matcher.py`, `scoring.py`, `resume.py`, `cover_letter.py`, and `quality.py` for AI and document workflows.
- `tracker.py` for local SQLite persistence.

## Future Backend Direction

Use a dedicated API backend when moving to SaaS. A conservative path is Python FastAPI because the existing business logic is already Python-based.

## Current Database

SQLite for local application tracking and ranking history.

## Future Database

PostgreSQL, preferably through Supabase or a managed Postgres provider, with row-level user ownership and audit-friendly application history.

## Authentication

Current: local/private alpha password and session-local tester profiles.

Future: Supabase Auth, Clerk, or another production auth provider with email login and optional Google OAuth.

## Hosting

Current:

- Streamlit local development.
- Streamlit Community Cloud/private alpha deployment.

Future:

- Web frontend on Vercel or equivalent.
- API/backend on Railway, Render, Fly.io, or a cloud container service.
- PostgreSQL on Supabase or managed Postgres.
- Object storage for generated PDFs.

## Third-Party APIs

Current and near-term:

- Anthropic or Gemini for structured AI generation.
- Greenhouse public job boards.
- Lever public postings.
- Ashby public job boards.
- Adzuna broad job API.
- Jooble broad job API.

Possible future:

- Licensed job data partner or search API for broader market coverage.
- Email service for daily alerts.
- Payment provider for SaaS subscriptions.

## Key Libraries

- Streamlit for UI.
- Requests/BeautifulSoup-style extraction for public pages.
- SQLite standard library for local persistence.
- ReportLab fallback for PDF generation.
- Pytest for regression tests.
- Anthropic/Gemini SDKs depending on selected provider.

## Environment Variables

- `LLM_PROVIDER`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `GREENHOUSE_BOARDS`
- `LEVER_SITES`
- `ASHBY_BOARDS`
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`
- `ADZUNA_COUNTRY`
- `JOOBLE_API_KEY`
- `JOOBLE_COUNTRY`
- `APP_PASSWORD`
- `APPLYSMART_ALPHA_MODE`
- `MAX_AI_ACTIONS_PER_SESSION`
- Candidate contact variables for local profile defaults.

Note: `APPLYSMART_*` environment variable names are legacy compatibility keys
kept during the PathPilot rebrand. Product-facing surfaces should use
PathPilot.

## Constraints

- Do not scrape LinkedIn, Naukri, Indeed, or similar platforms without approved access.
- Job discovery must preserve source attribution and original job URLs.
- The app must not automatically apply to jobs.
- AI output must not invent candidate experience or unsupported claims.
- Profile-derived job preferences must remain user-reviewable.
- Recommended jobs must prioritize entry-level/fresher evidence over raw keyword overlap.
- Provider failures should be isolated so one failing source does not break discovery.
