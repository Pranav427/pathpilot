# Document 06 - Implementation Plan

## Phase 1 - Stabilize Current Alpha

Goal: keep the current Streamlit product reliable while continuing product discovery.

Tasks:

- Keep resume and cover-letter generation stable.
- Preserve deterministic tests for safety, scoring, tracker, and Streamlit imports.
- Keep user-approved application tracking.
- Make profile-based job preferences clear and repeatable.

Done criteria:

- Full test suite passes.
- Manual flow works from job discovery to prepared application.
- No generated document claims unsupported candidate experience.

## Phase 2 - Improve Job Discovery Backbone

Goal: produce enough relevant jobs for real users without relying on one source.

Tasks:

- Expand curated Greenhouse, Lever, and Ashby company feeds.
- Improve source diagnostics so users know why provider coverage is weak.
- Keep Adzuna and Jooble as broad-market fallback sources.
- Improve entry-level detection and seniority filtering.
- Deduplicate noisy aggregator results.
- Add a source-quality score per job.
- Add provider-level tests for filtering, deduplication, freshness, and source failures.

Done criteria:

- Common broad searches return at least 10 usable jobs when market supply exists.
- Recommended results contain low seniority conflict.
- Source coverage does not depend almost entirely on one provider for every search.

## Phase 3 - Productize The Job Inbox

Goal: make job review feel like a real user workflow, not a raw list.

Tasks:

- Default to Recommended jobs.
- Show compact job cards with source, confidence, location, and action buttons.
- Collapse long descriptions.
- Add clear statuses: New, Shortlisted, Prepared, Ignored.
- Explain why a job is recommended or manual-review only.
- Make Prepare Application transfer only the selected job.

Done criteria:

- A new tester can understand and use the inbox without explanation.
- No user confuses job discovery with automatic applying.
- Original job and apply links are visible when available.

## Phase 4 - SaaS Backend Foundation

Goal: prepare the product for real accounts, saved data, and scheduled discovery.

Tasks:

- Choose auth provider.
- Choose PostgreSQL provider.
- Implement users, profiles, preferences, discovered jobs, discovery runs, recommendations, applications, documents, and outcomes.
- Move session-only profile data into persistent user-owned records.
- Add object storage for generated PDFs.
- Add background job ingestion design.

Done criteria:

- Each user has isolated profile, jobs, applications, and documents.
- Job discovery results can be stored, refreshed, and reused.
- Generated documents are private and retrievable.

## Phase 5 - Scheduled Discovery And Alerts

Goal: make PathPilot proactive.

Tasks:

- Run scheduled discovery for saved preferences.
- Store daily/weekly new matches.
- Notify users through email or dashboard alerts.
- Avoid re-showing ignored duplicates.
- Track source freshness and provider health.

Done criteria:

- User can save preferences once and see fresh job recommendations later.
- Duplicate and stale listings are controlled.
- Provider failures do not break the daily run.

## Phase 6 - Outcome Analytics

Goal: learn which applications and roles produce interviews.

Tasks:

- Add outcome statuses: applied, interview, rejected, offer, withdrawn.
- Track application date and response date.
- Show role/category conversion insights.
- Compare fit scores with real outcomes.
- Suggest better target roles and skill gaps based on history.

Done criteria:

- User can see which applications are working.
- Product can learn from outcomes without exposing private data.

## Phase 7 - Production UI

Goal: move from Streamlit alpha to a scalable SaaS interface.

Tasks:

- Design production dashboard.
- Build onboarding, profile editor, discovery inbox, application workspace, tracker, and analytics pages.
- Add responsive layouts.
- Add loading, empty, and error states.
- Add accessible component styling.

Done criteria:

- Core flows are usable on desktop and mobile.
- Visual design feels cohesive and trustworthy.
- Streamlit no longer blocks product-quality UX.

## Phase 8 - Deployment And Operations

Goal: launch safely on the internet.

Tasks:

- Configure production environment variables.
- Set up logging and error monitoring.
- Add rate limits for AI and provider APIs.
- Add privacy policy and terms.
- Set up backup strategy.
- Add smoke tests for deployment.

Done criteria:

- Production app can be shared publicly.
- Secrets are secure.
- Provider/API failures are observable.
- User data is protected.

## Build Order Recommendation

The next serious product work should follow this order:

1. Job discovery source expansion and quality.
2. Job inbox UX refinement.
3. Persistent SaaS backend schema.
4. Auth and user-owned profiles.
5. Scheduled discovery.
6. Outcome analytics.
7. Production frontend migration.
